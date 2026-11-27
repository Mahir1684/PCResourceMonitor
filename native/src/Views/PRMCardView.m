#import "PRMCardView.h"

@interface PRMCardView ()

@property (nonatomic, strong, readwrite) UILabel *titleLabel;
@property (nonatomic, strong, readwrite) UILabel *subtitleLabel;
@property (nonatomic, strong, readwrite) UILabel *badgeLabel;
@property (nonatomic, strong, readwrite) UIView *headerDivider;
@property (nonatomic, strong, readwrite) UIView *contentContainerView;

@end

@implementation PRMCardView

- (instancetype)initWithTitle:(NSString *)title subtitle:(NSString *)subtitle badge:(nullable NSString *)badge {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        // Dark solid surface with restrained border (opaque to eliminate GPU compositing overhead)
        self.opaque = YES;
        self.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        self.layer.borderColor = [UIColor colorWithRed:44.0/255.0 green:82.0/255.0 blue:130.0/255.0 alpha:0.35].CGColor;
        self.layer.borderWidth = 1.0;
        self.layer.cornerRadius = 8.0;
        self.layer.masksToBounds = NO;

        // Card Category Title (e.g. CPU COMPUTE)
        _titleLabel = [[UILabel alloc] init];
        _titleLabel.opaque = YES;
        _titleLabel.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        _titleLabel.text = [title uppercaseString];
        _titleLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
        _titleLabel.font = [UIFont boldSystemFontOfSize:11.0];
        [self addSubview:_titleLabel];

        // Specific hardware name (e.g. Intel Core i7-13700K)
        _subtitleLabel = [[UILabel alloc] init];
        _subtitleLabel.opaque = YES;
        _subtitleLabel.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        _subtitleLabel.text = subtitle;
        _subtitleLabel.textColor = [UIColor colorWithRed:226.0/255.0 green:232.0/255.0 blue:240.0/255.0 alpha:1.0];
        _subtitleLabel.font = [UIFont boldSystemFontOfSize:12.0];
        _subtitleLabel.lineBreakMode = NSLineBreakByTruncatingMiddle;
        [self addSubview:_subtitleLabel];

        // Top-right pill badge (e.g. 16C / 24T)
        _badgeLabel = [[UILabel alloc] init];
        _badgeLabel.textColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
        _badgeLabel.backgroundColor = [UIColor colorWithRed:15.0/255.0 green:45.0/255.0 blue:80.0/255.0 alpha:0.60];
        _badgeLabel.font = [UIFont boldSystemFontOfSize:10.0];
        _badgeLabel.textAlignment = NSTextAlignmentCenter;
        _badgeLabel.layer.cornerRadius = 3.0;
        _badgeLabel.layer.masksToBounds = YES;
        [self addSubview:_badgeLabel];
        [self setBadge:badge];

        // Header bottom divider line
        _headerDivider = [[UIView alloc] init];
        _headerDivider.backgroundColor = [UIColor colorWithRed:30.0/255.0 green:48.0/255.0 blue:80.0/255.0 alpha:0.40];
        [self addSubview:_headerDivider];

        // Content Container View
        _contentContainerView = [[UIView alloc] init];
        _contentContainerView.opaque = YES;
        _contentContainerView.backgroundColor = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];
        [self addSubview:_contentContainerView];
    }
    return self;
}

- (void)setSubtitle:(NSString *)subtitle {
    if ([self.subtitleLabel.text isEqualToString:subtitle]) return;
    self.subtitleLabel.text = subtitle;
}

- (void)setBadge:(nullable NSString *)badge {
    NSString *newBadge = (badge && badge.length > 0) ? [badge uppercaseString] : nil;
    if ((!self.badgeLabel.text && !newBadge) || [self.badgeLabel.text isEqualToString:newBadge]) {
        return;
    }
    if (newBadge) {
        self.badgeLabel.text = newBadge;
        self.badgeLabel.hidden = NO;
    } else {
        self.badgeLabel.text = nil;
        self.badgeLabel.hidden = YES;
    }
    [self setNeedsLayout];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat width = self.bounds.size.width;
    CGFloat height = self.bounds.size.height;
    CGFloat padding = 14.0;

    // Header layout
    CGFloat headerHeight = 44.0;
    self.titleLabel.frame = CGRectMake(padding, 8.0, width - (padding * 2) - 80.0, 14.0);

    CGFloat badgeWidth = 0.0;
    if (!self.badgeLabel.hidden && self.badgeLabel.text.length > 0) {
        badgeWidth = MAX(44.0, [self.badgeLabel.text sizeWithAttributes:@{NSFontAttributeName: self.badgeLabel.font}].width + 12.0);
        self.badgeLabel.frame = CGRectMake(width - padding - badgeWidth, 14.0, badgeWidth, 18.0);
    }

    CGFloat subtitleWidth = width - (padding * 2) - (badgeWidth > 0 ? badgeWidth + 8.0 : 0.0);
    self.subtitleLabel.frame = CGRectMake(padding, 24.0, subtitleWidth, 16.0);

    self.headerDivider.frame = CGRectMake(padding, headerHeight, width - (padding * 2), 1.0);

    // Content container layout
    self.contentContainerView.frame = CGRectMake(padding, headerHeight + 6.0, width - (padding * 2), height - headerHeight - 12.0);
}

@end
