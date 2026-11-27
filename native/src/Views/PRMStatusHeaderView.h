#import <UIKit/UIKit.h>
#import "../Services/PRMTelemetryClient.h"

NS_ASSUME_NONNULL_BEGIN

@interface PRMStatusHeaderView : UIView

@property (nonatomic, strong, readonly) UILabel *titleLabel;
@property (nonatomic, strong, readonly) UILabel *subtitleLabel;
@property (nonatomic, strong, readonly) UILabel *systemInfoLabel;
@property (nonatomic, strong, readonly) UILabel *statusBadgeLabel;
@property (nonatomic, strong, readonly) UILabel *timestampLabel;

- (instancetype)initWithFrame:(CGRect)frame;

- (void)updateWithConnectionState:(PRMConnectionState)state sequence:(uint64_t)seq timestamp:(nullable NSString *)timestamp;
- (void)setSystemHost:(NSString *)hostname osName:(NSString *)osName;

@end

NS_ASSUME_NONNULL_END
