#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface PRMTelemetryRow : UIView

@property (nonatomic, strong, readonly) UILabel *titleLabel;
@property (nonatomic, strong, readonly) UILabel *valueLabel;
@property (nonatomic, strong, readonly) UILabel *naBadgeLabel;

- (instancetype)initWithTitle:(NSString *)title;
- (void)setValueText:(nullable NSString *)text isAvailable:(BOOL)available;
- (void)setValueText:(NSString *)text;

@end

NS_ASSUME_NONNULL_END
