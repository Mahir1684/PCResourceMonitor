#import "PRMTelemetryRow.h"

@interface PRMTelemetryRow ()

@property (nonatomic, strong, readwrite) UILabel *titleLabel;
@property (nonatomic, strong, readwrite) UILabel *valueLabel;
@property (nonatomic, strong, readwrite) UILabel *naBadgeLabel;

@end

@implementation PRMTelemetryRow

- (instancetype)initWithTitle:(NSString *)title {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        self.opaque = YES;
        self.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

        _titleLabel = [[UILabel alloc] init];
        _titleLabel.opaque = YES;
        _titleLabel.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        _titleLabel.text = title;
        _titleLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
        _titleLabel.font = [UIFont systemFontOfSize:12.0];
        [self addSubview:_titleLabel];

        _valueLabel = [[UILabel alloc] init];
        _valueLabel.opaque = YES;
        _valueLabel.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        _valueLabel.text = @"--";
        _valueLabel.textColor = [UIColor colorWithRed:241.0/255.0 green:245.0/255.0 blue:249.0/255.0 alpha:1.0];
        _valueLabel.font = [UIFont boldSystemFontOfSize:12.0];
        _valueLabel.textAlignment = NSTextAlignmentRight;
        _valueLabel.numberOfLines = 1;
        _valueLabel.adjustsFontSizeToFitWidth = YES;
        _valueLabel.minimumScaleFactor = 0.75;
        _valueLabel.baselineAdjustment = UIBaselineAdjustmentAlignCenters;
        [self addSubview:_valueLabel];

        _naBadgeLabel = [[UILabel alloc] init];
        _naBadgeLabel.text = @"N/A";
        _naBadgeLabel.textColor = [UIColor colorWithRed:148.0/255.0 green:163.0/255.0 blue:184.0/255.0 alpha:1.0];
        _naBadgeLabel.backgroundColor = [UIColor colorWithRed:30.0/255.0 green:41.0/255.0 blue:59.0/255.0 alpha:0.80];
        _naBadgeLabel.font = [UIFont boldSystemFontOfSize:10.0];
        _naBadgeLabel.textAlignment = NSTextAlignmentCenter;
        _naBadgeLabel.layer.cornerRadius = 3.0;
        _naBadgeLabel.layer.masksToBounds = YES;
        _naBadgeLabel.hidden = YES;
        [self addSubview:_naBadgeLabel];
    }
    return self;
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat width = self.bounds.size.width;
    CGFloat height = self.bounds.size.height;

    self.titleLabel.frame = CGRectMake(0, 0, width * 0.35, height);

    CGFloat badgeWidth = 32.0;
    CGFloat badgeHeight = 16.0;
    self.naBadgeLabel.frame = CGRectMake(width - badgeWidth, (height - badgeHeight) / 2.0, badgeWidth, badgeHeight);

    if (self.naBadgeLabel.hidden) {
        self.valueLabel.frame = CGRectMake(width * 0.35, 0, width * 0.65, height);
    } else {
        self.valueLabel.frame = CGRectMake(width * 0.35, 0, width * 0.65 - badgeWidth - 6.0, height);
    }
}

- (void)setValueText:(nullable NSString *)text isAvailable:(BOOL)available {
    NSString *targetText = (available && text.length > 0) ? text : (text.length > 0 ? text : @"--");
    BOOL targetNaHidden = (available && text.length > 0);

    // Skip redundant updates and avoid triggering unnecessary layout passes
    if ([self.valueLabel.text isEqualToString:targetText] && self.naBadgeLabel.hidden == targetNaHidden) {
        return;
    }

    BOOL naVisibilityChanged = (self.naBadgeLabel.hidden != targetNaHidden);
    self.valueLabel.text = targetText;

    if (targetNaHidden) {
        self.valueLabel.textColor = [UIColor colorWithRed:241.0/255.0 green:245.0/255.0 blue:249.0/255.0 alpha:1.0];
        self.naBadgeLabel.hidden = YES;
    } else {
        self.valueLabel.textColor = [UIColor colorWithRed:100.0/255.0 green:116.0/255.0 blue:139.0/255.0 alpha:1.0];
        self.naBadgeLabel.hidden = NO;
    }

    if (naVisibilityChanged) {
        [self setNeedsLayout];
    }
}

- (void)setValueText:(NSString *)text {
    [self setValueText:text isAvailable:(text.length > 0 && ![text isEqualToString:@"--"])];
}

@end
