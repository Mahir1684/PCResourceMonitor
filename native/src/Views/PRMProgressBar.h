#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface PRMProgressBar : UIView

@property (nonatomic, assign) CGFloat progress; // 0.0 to 1.0
@property (nonatomic, strong) UIColor *fillColor;
@property (nonatomic, strong) UIColor *trackColor;
@property (nonatomic, assign) BOOL useThresholdColors; // Changes to amber at 75%, red at 90%

- (instancetype)initWithFrame:(CGRect)frame;
- (void)setProgress:(CGFloat)progress animated:(BOOL)animated;

@end

NS_ASSUME_NONNULL_END
