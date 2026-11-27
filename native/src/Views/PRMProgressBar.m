#import "PRMProgressBar.h"

@interface PRMProgressBar ()

@property (nonatomic, strong) UIView *fillView;

@end

@implementation PRMProgressBar

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        _progress = 0.0;
        _useThresholdColors = NO;
        _trackColor = [UIColor colorWithRed:22.0/255.0 green:34.0/255.0 blue:56.0/255.0 alpha:1.0];
        _fillColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0]; // Default cyan

        self.opaque = YES;
        self.backgroundColor = _trackColor;
        self.layer.masksToBounds = YES;

        _fillView = [[UIView alloc] initWithFrame:CGRectZero];
        _fillView.opaque = YES;
        _fillView.backgroundColor = _fillColor;
        [self addSubview:_fillView];
    }
    return self;
}

- (void)layoutSubviews {
    [super layoutSubviews];
    self.layer.cornerRadius = self.bounds.size.height / 2.0;
    self.fillView.layer.cornerRadius = self.bounds.size.height / 2.0;
    [self updateFillFrameAnimated:NO];
}

- (void)setProgress:(CGFloat)progress {
    [self setProgress:progress animated:NO];
}

- (void)setProgress:(CGFloat)progress animated:(BOOL)animated {
    CGFloat clamped = MAX(0.0, MIN(1.0, progress));
    if (fabs(_progress - clamped) < 0.003 && self.fillView.frame.size.height > 0) {
        return;
    }
    _progress = clamped;
    [self updateFillFrameAnimated:animated];
}

- (void)setFillColor:(UIColor *)fillColor {
    _fillColor = fillColor;
    if (!self.useThresholdColors) {
        self.fillView.backgroundColor = fillColor;
    }
}

- (void)setTrackColor:(UIColor *)trackColor {
    _trackColor = trackColor;
    self.backgroundColor = trackColor;
}

- (void)updateFillFrameAnimated:(BOOL)animated {
    CGFloat fillWidth = self.bounds.size.width * _progress;
    CGRect targetFrame = CGRectMake(0, 0, fillWidth, self.bounds.size.height);

    if (self.useThresholdColors) {
        UIColor *targetColor = nil;
        if (_progress >= 0.90) {
            targetColor = [UIColor colorWithRed:239.0/255.0 green:68.0/255.0 blue:68.0/255.0 alpha:1.0]; // Red
        } else if (_progress >= 0.75) {
            targetColor = [UIColor colorWithRed:245.0/255.0 green:158.0/255.0 blue:11.0/255.0 alpha:1.0]; // Amber
        } else {
            targetColor = self.fillColor;
        }
        if (self.fillView.backgroundColor != targetColor) {
            self.fillView.backgroundColor = targetColor;
        }
    } else {
        if (self.fillView.backgroundColor != self.fillColor) {
            self.fillView.backgroundColor = self.fillColor;
        }
    }

    if (CGRectEqualToRect(self.fillView.frame, targetFrame)) {
        return;
    }

    if (animated && self.fillView.frame.size.height > 0) {
        [UIView animateWithDuration:0.25 delay:0 options:UIViewAnimationOptionCurveEaseOut animations:^{
            self.fillView.frame = targetFrame;
        } completion:nil];
    } else {
        self.fillView.frame = targetFrame;
    }
}

@end
