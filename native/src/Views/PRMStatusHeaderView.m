#import "PRMStatusHeaderView.h"

@interface PRMStatusHeaderView ()

@property (nonatomic, strong, readwrite) UILabel *titleLabel;
@property (nonatomic, strong, readwrite) UILabel *subtitleLabel;
@property (nonatomic, strong, readwrite) UILabel *systemInfoLabel;
@property (nonatomic, strong, readwrite) UILabel *statusBadgeLabel;
@property (nonatomic, strong, readwrite) UILabel *timestampLabel;

@end

@implementation PRMStatusHeaderView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.opaque = YES;
        self.backgroundColor = [UIColor colorWithRed:12.0/255.0 green:18.0/255.0 blue:32.0/255.0 alpha:1.0];
        self.layer.borderColor = [UIColor colorWithRed:36.0/255.0 green:64.0/255.0 blue:105.0/255.0 alpha:0.40].CGColor;
        self.layer.borderWidth = 1.0;
        self.layer.cornerRadius = 8.0;
        self.layer.masksToBounds = NO;

        // Title
        _titleLabel = [[UILabel alloc] init];
        _titleLabel.opaque = YES;
        _titleLabel.backgroundColor = self.backgroundColor;
        _titleLabel.text = @"PC RESOURCE MONITOR";
        _titleLabel.textColor = [UIColor whiteColor];
        _titleLabel.font = [UIFont boldSystemFontOfSize:15.0];
        [self addSubview:_titleLabel];

        // Subtitle / Tunnel note
        _subtitleLabel = [[UILabel alloc] init];
        _subtitleLabel.opaque = YES;
        _subtitleLabel.backgroundColor = self.backgroundColor;
        _subtitleLabel.text = @"USB TUNNEL • 127.0.0.1:5002";
        _subtitleLabel.textColor = [UIColor colorWithRed:100.0/255.0 green:116.0/255.0 blue:139.0/255.0 alpha:1.0];
        _subtitleLabel.font = [UIFont systemFontOfSize:11.0];
        [self addSubview:_subtitleLabel];

        // System info (center)
        _systemInfoLabel = [[UILabel alloc] init];
        _systemInfoLabel.opaque = YES;
        _systemInfoLabel.backgroundColor = self.backgroundColor;
        _systemInfoLabel.text = @"HOST: PC • WINDOWS 11";
        _systemInfoLabel.textColor = [UIColor colorWithRed:148.0/255.0 green:163.0/255.0 blue:184.0/255.0 alpha:1.0];
        _systemInfoLabel.font = [UIFont boldSystemFontOfSize:11.0];
        _systemInfoLabel.textAlignment = NSTextAlignmentCenter;
        [self addSubview:_systemInfoLabel];

        // Status Badge Pill
        _statusBadgeLabel = [[UILabel alloc] init];
        _statusBadgeLabel.text = @"CONNECTING";
        _statusBadgeLabel.textColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
        _statusBadgeLabel.backgroundColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:0.15];
        _statusBadgeLabel.layer.borderColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:0.40].CGColor;
        _statusBadgeLabel.layer.borderWidth = 1.0;
        _statusBadgeLabel.layer.cornerRadius = 4.0;
        _statusBadgeLabel.layer.masksToBounds = YES;
        _statusBadgeLabel.font = [UIFont boldSystemFontOfSize:11.0];
        _statusBadgeLabel.textAlignment = NSTextAlignmentCenter;
        [self addSubview:_statusBadgeLabel];

        // Timestamp / Sequence
        _timestampLabel = [[UILabel alloc] init];
        _timestampLabel.opaque = YES;
        _timestampLabel.backgroundColor = self.backgroundColor;
        _timestampLabel.text = @"Connecting...";
        _timestampLabel.textColor = [UIColor colorWithRed:148.0/255.0 green:163.0/255.0 blue:184.0/255.0 alpha:1.0];
        _timestampLabel.font = [UIFont systemFontOfSize:11.0];
        _timestampLabel.textAlignment = NSTextAlignmentRight;
        [self addSubview:_timestampLabel];
    }
    return self;
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat width = self.bounds.size.width;
    CGFloat height = self.bounds.size.height;
    CGFloat pad = 14.0;

    // Left title group
    self.titleLabel.frame = CGRectMake(pad, 7.0, 240.0, 18.0);
    self.subtitleLabel.frame = CGRectMake(pad, 25.0, 240.0, 14.0);

    // Center system info
    CGFloat centerWidth = 320.0;
    self.systemInfoLabel.frame = CGRectMake((width - centerWidth) / 2.0, (height - 18.0) / 2.0, centerWidth, 18.0);

    // Right status group
    CGFloat badgeWidth = 92.0;
    CGFloat badgeHeight = 22.0;
    CGFloat badgeX = width - pad - badgeWidth;
    CGFloat badgeY = (height - badgeHeight) / 2.0;
    self.statusBadgeLabel.frame = CGRectMake(badgeX, badgeY, badgeWidth, badgeHeight);

    CGFloat timeWidth = 170.0;
    CGFloat timeX = badgeX - timeWidth - 10.0;
    self.timestampLabel.frame = CGRectMake(timeX, (height - 18.0) / 2.0, timeWidth, 18.0);
}

- (void)setSystemHost:(NSString *)hostname osName:(NSString *)osName {
    NSString *cleanHost = (hostname.length > 0) ? hostname : @"PC";
    NSString *cleanOs = (osName.length > 0) ? osName : @"WINDOWS";
    NSString *target = [[NSString stringWithFormat:@"%@ • %@", cleanHost, cleanOs] uppercaseString];
    if ([self.systemInfoLabel.text isEqualToString:target]) {
        return;
    }
    self.systemInfoLabel.text = target;
}

- (void)updateWithConnectionState:(PRMConnectionState)state sequence:(uint64_t)seq timestamp:(nullable NSString *)timestamp {
    NSString *text = NSStringFromPRMConnectionState(state);

    if (![self.statusBadgeLabel.text isEqualToString:text]) {
        UIColor *fg = nil;
        UIColor *bg = nil;

        switch (state) {
            case PRMConnectionStateLive:
                fg = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0]; // #10b981
                bg = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:0.18];
                break;
            case PRMConnectionStateConnecting:
                fg = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0]; // #00d2ff
                bg = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:0.18];
                break;
            case PRMConnectionStateStale:
                fg = [UIColor colorWithRed:245.0/255.0 green:158.0/255.0 blue:11.0/255.0 alpha:1.0]; // #f59e0b
                bg = [UIColor colorWithRed:245.0/255.0 green:158.0/255.0 blue:11.0/255.0 alpha:0.18];
                break;
            case PRMConnectionStateOffline:
                fg = [UIColor colorWithRed:239.0/255.0 green:68.0/255.0 blue:68.0/255.0 alpha:1.0]; // #ef4444
                bg = [UIColor colorWithRed:239.0/255.0 green:68.0/255.0 blue:68.0/255.0 alpha:0.18];
                break;
            case PRMConnectionStateReconnecting:
                fg = [UIColor colorWithRed:249.0/255.0 green:115.0/255.0 blue:22.0/255.0 alpha:1.0]; // #f97316
                bg = [UIColor colorWithRed:249.0/255.0 green:115.0/255.0 blue:22.0/255.0 alpha:0.18];
                break;
        }

        self.statusBadgeLabel.text = text;
        self.statusBadgeLabel.textColor = fg;
        self.statusBadgeLabel.backgroundColor = bg;
        self.statusBadgeLabel.layer.borderColor = [fg colorWithAlphaComponent:0.40].CGColor;
    }

    if (seq > 0) {
        NSString *timeStr = timestamp ?: @"";
        // Extract HH:mm:ss if ISO timestamp (e.g. 2026-11-19T06:12:34Z)
        if (timeStr.length >= 19 && [timeStr containsString:@"T"]) {
            timeStr = [timeStr substringWithRange:NSMakeRange(11, 8)];
        }
        NSString *targetTime = [NSString stringWithFormat:@"Seq #%llu • %@", seq, timeStr.length > 0 ? timeStr : @"Live"];
        if (![self.timestampLabel.text isEqualToString:targetTime]) {
            self.timestampLabel.text = targetTime;
        }
    } else {
        if (![self.timestampLabel.text isEqualToString:@"Waiting for telemetry..."]) {
            self.timestampLabel.text = @"Waiting for telemetry...";
        }
    }
}

@end
