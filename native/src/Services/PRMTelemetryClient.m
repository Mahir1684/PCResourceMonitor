#import "PRMTelemetryClient.h"
#import <UIKit/UIKit.h>

NSString *NSStringFromPRMConnectionState(PRMConnectionState state) {
    switch (state) {
        case PRMConnectionStateConnecting:
            return @"CONNECTING";
        case PRMConnectionStateLive:
            return @"LIVE";
        case PRMConnectionStateStale:
            return @"STALE";
        case PRMConnectionStateOffline:
            return @"OFFLINE";
        case PRMConnectionStateReconnecting:
            return @"RECONNECTING";
    }
}

static NSTimeInterval const kPRMPollInterval = 1.0;
static NSTimeInterval const kPRMRequestTimeout = 2.0;
static NSTimeInterval const kPRMResourceTimeout = 2.0;
static NSTimeInterval const kPRMStaleThreshold = 3.0;
static NSInteger const kPRMOfflineFailureThreshold = 3;

@interface PRMTelemetryClient ()

@property (nonatomic, assign, readwrite) PRMConnectionState connectionState;
@property (nonatomic, assign, readwrite) uint64_t lastSequence;
@property (nonatomic, assign, readwrite) NSInteger consecutiveFailures;
@property (nonatomic, strong, readwrite) NSURL *endpointURL;
@property (nonatomic, assign, readwrite) BOOL isPolling;

@property (nonatomic, strong) NSURLSession *session;
@property (nonatomic, strong, nullable) NSTimer *pollTimer;
@property (nonatomic, strong, nullable) NSURLSessionDataTask *currentTask;
@property (nonatomic, assign) BOOL isRequestInFlight;
@property (nonatomic, assign) NSTimeInterval inFlightRequestStartTime;
@property (nonatomic, assign) NSTimeInterval lastSuccessTimestamp;
@property (nonatomic, assign) BOOL wasPollingBeforeBackground;

@property (nonatomic, assign) uint64_t requestCounter;
@property (nonatomic, assign) uint64_t activeRequestId;

@end

@implementation PRMTelemetryClient

+ (instancetype)defaultClient {
    static PRMTelemetryClient *sharedClient = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:5002/api/v1/status"];
        sharedClient = [[PRMTelemetryClient alloc] initWithEndpointURL:url];
    });
    return sharedClient;
}

- (instancetype)initWithEndpointURL:(NSURL *)url {
    self = [super init];
    if (self) {
        _endpointURL = url;
        _connectionState = PRMConnectionStateConnecting;
        _lastSequence = 0;
        _consecutiveFailures = 0;
        _lastSuccessTimestamp = 0;
        _isRequestInFlight = NO;
        _inFlightRequestStartTime = 0;
        _isPolling = NO;
        _requestCounter = 0;
        _activeRequestId = 0;

        NSURLSessionConfiguration *config = [NSURLSessionConfiguration ephemeralSessionConfiguration];
        config.requestCachePolicy = NSURLRequestReloadIgnoringLocalCacheData;
        config.timeoutIntervalForRequest = kPRMRequestTimeout;
        config.timeoutIntervalForResource = kPRMResourceTimeout;
        config.HTTPShouldSetCookies = NO;
        config.HTTPCookieAcceptPolicy = NSHTTPCookieAcceptPolicyNever;
        _session = [NSURLSession sessionWithConfiguration:config];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(handleAppWillResignActive:)
                                                     name:UIApplicationWillResignActiveNotification
                                                   object:nil];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(handleAppDidBecomeActive:)
                                                     name:UIApplicationDidBecomeActiveNotification
                                                   object:nil];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(handleAppDidEnterBackground:)
                                                     name:UIApplicationDidEnterBackgroundNotification
                                                   object:nil];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(handleAppWillEnterForeground:)
                                                     name:UIApplicationWillEnterForegroundNotification
                                                   object:nil];
    }
    return self;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
    [self stopPolling];
    [_session invalidateAndCancel];
}

#pragma mark - State Management

- (void)setConnectionState:(PRMConnectionState)newState {
    if (_connectionState != newState) {
        _connectionState = newState;
        NSLog(@"[PRMTelemetryClient] State transitioned to: %@", NSStringFromPRMConnectionState(newState));
        if ([self.delegate respondsToSelector:@selector(telemetryClient:didChangeConnectionState:)]) {
            [self.delegate telemetryClient:self didChangeConnectionState:newState];
        }
    }
}

#pragma mark - Polling Control

- (void)startPolling {
    if (_isPolling) return;
    _isPolling = YES;

    NSLog(@"[PRMTelemetryClient] Starting telemetry polling at %@ (interval: %.1fs)",
          self.endpointURL.absoluteString, kPRMPollInterval);

    self.pollTimer = [NSTimer timerWithTimeInterval:kPRMPollInterval
                                             target:self
                                           selector:@selector(pollTimerTick:)
                                           userInfo:nil
                                            repeats:YES];
    [[NSRunLoop mainRunLoop] addTimer:self.pollTimer forMode:NSRunLoopCommonModes];

    [self pollImmediately];
}

- (void)stopPolling {
    if (!_isPolling) return;
    _isPolling = NO;

    NSLog(@"[PRMTelemetryClient] Stopping telemetry polling");
    if (self.pollTimer) {
        [self.pollTimer invalidate];
        self.pollTimer = nil;
    }

    // Invalidate active request identity before cancelling
    self.activeRequestId = 0;
    if (self.currentTask) {
        [self.currentTask cancel];
        self.currentTask = nil;
    }
    self.isRequestInFlight = NO;
    self.inFlightRequestStartTime = 0;
}

- (void)pollImmediately {
    if (!_isPolling) return;
    [self performPoll];
}

- (void)pollTimerTick:(NSTimer *)timer {
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];

    // Check for data staleness
    if (self.connectionState == PRMConnectionStateLive && self.lastSuccessTimestamp > 0) {
        if ((now - self.lastSuccessTimestamp) >= kPRMStaleThreshold) {
            [self setConnectionState:PRMConnectionStateStale];
        }
    } else if (self.connectionState == PRMConnectionStateOffline) {
        // Enter RECONNECTING once when beginning recovery probe from OFFLINE
        [self setConnectionState:PRMConnectionStateReconnecting];
    }

    // Guard against stalled in-flight requests (e.g. stalled socket across unplugged USB cable)
    if (self.isRequestInFlight) {
        if (self.inFlightRequestStartTime > 0 && (now - self.inFlightRequestStartTime) > (kPRMRequestTimeout + 0.5)) {
            NSLog(@"[PRMTelemetryClient] Request %llu stalled (%.1fs); resetting task and session",
                  self.activeRequestId, now - self.inFlightRequestStartTime);
            [self.currentTask cancel];
            self.currentTask = nil;
            self.isRequestInFlight = NO;
            self.inFlightRequestStartTime = 0;
            [self.session resetWithCompletionHandler:^{}];
        } else {
            return;
        }
    }

    [self performPoll];
}

#pragma mark - Network Execution

- (void)performPoll {
    if (self.isRequestInFlight) {
        // Drop tick if previous request is still in flight across the USB link
        return;
    }

    self.isRequestInFlight = YES;
    self.inFlightRequestStartTime = [NSDate timeIntervalSinceReferenceDate];
    uint64_t requestId = ++self.requestCounter;
    self.activeRequestId = requestId;

    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:self.endpointURL
                                                           cachePolicy:NSURLRequestReloadIgnoringLocalCacheData
                                                       timeoutInterval:kPRMRequestTimeout];
    [request setHTTPMethod:@"GET"];
    [request setValue:@"application/json" forHTTPHeaderField:@"Accept"];
    [request setValue:@"close" forHTTPHeaderField:@"Connection"];

    __weak typeof(self) weakSelf = self;
    self.currentTask = [self.session dataTaskWithRequest:request
                                       completionHandler:^(NSData * _Nullable data,
                                                           NSURLResponse * _Nullable response,
                                                           NSError * _Nullable error) {
        // Early exit on cancellation without parsing
        if (error && error.code == NSURLErrorCancelled) {
            return;
        }

        PRMTelemetrySnapshot *snapshot = nil;
        NSError *resultError = error;

        // Perform JSON deserialization on background queue
        if (!resultError) {
            NSHTTPURLResponse *httpResp = (NSHTTPURLResponse *)response;
            if ([httpResp isKindOfClass:[NSHTTPURLResponse class]] && httpResp.statusCode == 200) {
                NSError *parseError = nil;
                snapshot = [PRMTelemetrySnapshot snapshotFromJSONData:data error:&parseError];
                if (!snapshot) {
                    resultError = parseError ?: [NSError errorWithDomain:@"PRMTelemetryErrorDomain"
                                                                    code:1003
                                                                userInfo:@{NSLocalizedDescriptionKey: @"Malformed telemetry JSON"}];
                }
            } else {
                NSInteger code = [httpResp isKindOfClass:[NSHTTPURLResponse class]] ? httpResp.statusCode : -1;
                resultError = [NSError errorWithDomain:@"PRMTelemetryErrorDomain"
                                                  code:code
                                              userInfo:@{NSLocalizedDescriptionKey: [NSString stringWithFormat:@"HTTP status %ld", (long)code]}];
            }
        }

        // Deliver result to main thread
        dispatch_async(dispatch_get_main_queue(), ^{
            [weakSelf handlePollResultWithSnapshot:snapshot
                                             error:resultError
                                         requestId:requestId];
        });
    }];

    [self.currentTask resume];
}

- (void)handlePollResultWithSnapshot:(nullable PRMTelemetrySnapshot *)snapshot
                               error:(nullable NSError *)error
                           requestId:(uint64_t)requestId {
    // Stale or cancelled completion callback isolation:
    // Only the currently active request identity may alter client state
    if (requestId == 0 || requestId != self.activeRequestId) {
        return;
    }

    self.isRequestInFlight = NO;
    self.inFlightRequestStartTime = 0;
    self.currentTask = nil;

    // Ignore cancellation errors without changing failure counters or state
    if (error && error.code == NSURLErrorCancelled) {
        return;
    }

    if (!self.isPolling) {
        return;
    }

    if (snapshot) {
        uint64_t seq = snapshot.sequence;

        // Server restart detection:
        // - Sequence 1 is accepted as a reset only when previous sequence > 1.
        // - Duplicate sequence 1 is rejected (when lastSequence == 1).
        // - Lower sequence accepted after consecutive failures (recovery from failure/restart).
        BOOL isReset = (seq == 1 && self.lastSequence > 1) ||
                       (seq < self.lastSequence && self.consecutiveFailures > 0);

        if (seq <= self.lastSequence && !isReset) {
            NSLog(@"[PRMTelemetryClient] Dropping duplicate or out-of-order sequence (incoming=%llu, last=%llu)",
                  seq, self.lastSequence);
            return;
        }

        if (isReset && self.lastSequence > 0) {
            NSLog(@"[PRMTelemetryClient] Detected server restart / sequence reset (%llu -> %llu)",
                  self.lastSequence, seq);
        }

        self.lastSequence = seq;
        self.lastSuccessTimestamp = [NSDate timeIntervalSinceReferenceDate];
        self.consecutiveFailures = 0;

        [self setConnectionState:PRMConnectionStateLive];

        if ([self.delegate respondsToSelector:@selector(telemetryClient:didReceiveSnapshot:)]) {
            [self.delegate telemetryClient:self didReceiveSnapshot:snapshot];
        }
    } else {
        self.consecutiveFailures++;
        NSLog(@"[PRMTelemetryClient] Network poll error (%ld consecutive): %@",
              (long)self.consecutiveFailures, error.localizedDescription);

        // Discard any stale/dead keep-alive sockets immediately so next attempt opens a new connection
        [self.session resetWithCompletionHandler:^{}];

        if (self.connectionState == PRMConnectionStateReconnecting) {
            // Remain in RECONNECTING during subsequent failed retry probes
            // Do not flap between OFFLINE and RECONNECTING on each tick
        } else if (self.consecutiveFailures >= kPRMOfflineFailureThreshold) {
            [self setConnectionState:PRMConnectionStateOffline];
        } else if (self.connectionState == PRMConnectionStateLive) {
            [self setConnectionState:PRMConnectionStateStale];
        }

        if ([self.delegate respondsToSelector:@selector(telemetryClient:didFailWithError:)]) {
            [self.delegate telemetryClient:self didFailWithError:error];
        }
    }
}

#pragma mark - App Lifecycle Handlers

- (void)handleAppWillResignActive:(NSNotification *)note {
    NSLog(@"[PRMTelemetryClient] App will resign active (Notification Center / overlay). Suspending polling.");
    if (self.isPolling) {
        self.wasPollingBeforeBackground = YES;
        [self stopPolling];
    }
}

- (void)handleAppDidBecomeActive:(NSNotification *)note {
    NSLog(@"[PRMTelemetryClient] App became active. Resuming polling.");
    if (self.wasPollingBeforeBackground && !self.isPolling) {
        [self startPolling];
    }
}

- (void)handleAppDidEnterBackground:(NSNotification *)note {
    NSLog(@"[PRMTelemetryClient] App entered background. Suspending polling.");
    if (self.isPolling) {
        self.wasPollingBeforeBackground = YES;
        [self stopPolling];
    }
}

- (void)handleAppWillEnterForeground:(NSNotification *)note {
    NSLog(@"[PRMTelemetryClient] App returning to foreground.");
    if (self.wasPollingBeforeBackground && !self.isPolling) {
        [self startPolling];
    }
}

@end
