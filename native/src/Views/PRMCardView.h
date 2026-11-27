#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface PRMCardView : UIView

@property (nonatomic, strong, readonly) UILabel *titleLabel;
@property (nonatomic, strong, readonly) UILabel *subtitleLabel;
@property (nonatomic, strong, readonly) UILabel *badgeLabel;
@property (nonatomic, strong, readonly) UIView *headerDivider;
@property (nonatomic, strong, readonly) UIView *contentContainerView;

- (instancetype)initWithTitle:(NSString *)title subtitle:(NSString *)subtitle badge:(nullable NSString *)badge;

- (void)setSubtitle:(NSString *)subtitle;
- (void)setBadge:(nullable NSString *)badge;

@end

NS_ASSUME_NONNULL_END
