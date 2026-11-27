#import <Foundation/Foundation.h>
#import "../Models/PRMTelemetrySnapshot.h"

NS_ASSUME_NONNULL_BEGIN

typedef NS_ENUM(NSInteger, PRMConnectionState) {
    PRMConnectionStateConnecting = 0,
    PRMConnectionStateLive,
    PRMConnectionStateStale,
    PRMConnectionStateOffline,
    PRMConnectionStateReconnecting
};

FOUNDATION_EXPORT NSString *NSStringFromPRMConnectionState(PRMConnectionState state);

@class PRMTelemetryClient;

@protocol PRMTelemetryClientDelegate <NSObject>
@optional
- (void)telemetryClient:(PRMTelemetryClient *)client didReceiveSnapshot:(PRMTelemetrySnapshot *)snapshot;
- (void)telemetryClient:(PRMTelemetryClient *)client didChangeConnectionState:(PRMConnectionState)state;
- (void)telemetryClient:(PRMTelemetryClient *)client didFailWithError:(NSError *)error;
@end

@interface PRMTelemetryClient : NSObject

@property (nonatomic, weak, nullable) id<PRMTelemetryClientDelegate> delegate;
@property (nonatomic, assign, readonly) PRMConnectionState connectionState;
@property (nonatomic, assign, readonly) uint64_t lastSequence;
@property (nonatomic, assign, readonly) NSInteger consecutiveFailures;
@property (nonatomic, strong, readonly) NSURL *endpointURL;
@property (nonatomic, assign, readonly) BOOL isPolling;

- (instancetype)initWithEndpointURL:(NSURL *)url;
+ (instancetype)defaultClient;

- (void)startPolling;
- (void)stopPolling;
- (void)pollImmediately;

@end

NS_ASSUME_NONNULL_END
