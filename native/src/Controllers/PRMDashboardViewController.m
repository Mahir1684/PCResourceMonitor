#import "PRMDashboardViewController.h"
#import "../Services/PRMTelemetryClient.h"
#import "../Models/PRMTelemetrySnapshot.h"
#import "../Views/PRMProgressBar.h"
#import "../Views/PRMCardView.h"
#import "../Views/PRMTelemetryRow.h"
#import "../Views/PRMStatusHeaderView.h"

#pragma mark - Formatting Utilities

static NSString *FormatBytes(uint64_t bytes) {
    if (bytes == 0) return @"--";
    double b = (double)bytes;
    if (b < 1024.0) return [NSString stringWithFormat:@"%.0f B", b];
    if (b < 1048576.0) return [NSString stringWithFormat:@"%.1f KB", b / 1024.0];
    if (b < 1073741824.0) return [NSString stringWithFormat:@"%.1f MB", b / 1048576.0];
    if (b < 1099511627776.0) return [NSString stringWithFormat:@"%.1f GB", b / 1073741824.0];
    return [NSString stringWithFormat:@"%.2f TB", b / 1099511627776.0];
}

static NSString *FormatRate(NSNumber * _Nullable rateNum) {
    if (!rateNum) return @"--";
    double r = [rateNum doubleValue];
    if (r < 0) return @"0 B/s";
    if (r < 1024.0) return [NSString stringWithFormat:@"%.0f B/s", r];
    if (r < 1048576.0) return [NSString stringWithFormat:@"%.1f KB/s", r / 1024.0];
    if (r < 1073741824.0) return [NSString stringWithFormat:@"%.1f MB/s", r / 1048576.0];
    return [NSString stringWithFormat:@"%.2f GB/s", r / 1073741824.0];
}

static NSString *FormatUptime(NSNumber * _Nullable uptimeSec) {
    if (!uptimeSec) return @"--";
    uint64_t s = [uptimeSec unsignedLongLongValue];
    uint64_t days = s / 86400;
    s %= 86400;
    uint64_t hours = s / 3600;
    s %= 3600;
    uint64_t minutes = s / 60;
    uint64_t secs = s % 60;
    if (days > 0) {
        return [NSString stringWithFormat:@"%llud %lluh %llum", days, hours, minutes];
    }
    return [NSString stringWithFormat:@"%02llu:%02llu:%02llu", hours, minutes, secs];
}

@interface PRMDashboardViewController () <PRMTelemetryClientDelegate>

@property (nonatomic, strong) PRMTelemetryClient *telemetryClient;
@property (nonatomic, strong) PRMStatusHeaderView *headerView;

// Card 1: CPU
@property (nonatomic, strong) PRMCardView *cpuCard;
@property (nonatomic, strong) UILabel *cpuPercentLabel;
@property (nonatomic, strong) UILabel *cpuPercentSymbol;
@property (nonatomic, strong) UILabel *cpuSubtextLabel;
@property (nonatomic, strong) PRMProgressBar *cpuProgressBar;
@property (nonatomic, strong) PRMTelemetryRow *cpuFreqRow;
@property (nonatomic, strong) PRMTelemetryRow *cpuTopologyRow;
@property (nonatomic, strong) UIView *coreMatrixContainer;
@property (nonatomic, strong) NSMutableArray<UIView *> *coreBarTracks;
@property (nonatomic, strong) NSMutableArray<UIView *> *coreBarFills;

// Card 2: Primary GPU (NVIDIA GeForce)
@property (nonatomic, strong) PRMCardView *nvidiaCard;
@property (nonatomic, strong) UILabel *gpuNvidiaPercentLabel;
@property (nonatomic, strong) UILabel *gpuNvidiaPercentSymbol;
@property (nonatomic, strong) UILabel *gpuNvidiaSubtextLabel;
@property (nonatomic, strong) UILabel *gpuNvidiaNotDetectedLabel;
@property (nonatomic, strong) PRMProgressBar *gpuNvidiaProgressBar;
@property (nonatomic, strong) PRMTelemetryRow *gpuNvidiaClockRow;
@property (nonatomic, strong) PRMTelemetryRow *gpuNvidiaPowerRow;
@property (nonatomic, strong) PRMTelemetryRow *gpuNvidiaTempRow;
@property (nonatomic, strong) PRMTelemetryRow *gpuNvidiaVramRow;
@property (nonatomic, strong) PRMProgressBar *gpuNvidiaVramBar;

// Card 3: Gaming & FPS (PresentMon ETW)
@property (nonatomic, strong) PRMCardView *fpsCard;
@property (nonatomic, strong) UILabel *fpsHeroLabel;
@property (nonatomic, strong) UILabel *fpsHeroUnit;
@property (nonatomic, strong) UILabel *fpsHeroSubtext;
@property (nonatomic, strong) PRMProgressBar *fpsProgressBar;
@property (nonatomic, strong) PRMTelemetryRow *fpsProcessRow;
@property (nonatomic, strong) PRMTelemetryRow *fpsFrameTimeRow;
@property (nonatomic, strong) PRMTelemetryRow *fpsApiRow;
@property (nonatomic, strong) PRMTelemetryRow *fpsStatusRow;

// Card 3: Memory
@property (nonatomic, strong) PRMCardView *memoryCard;
@property (nonatomic, strong) UILabel *ramPercentLabel;
@property (nonatomic, strong) UILabel *ramPercentSymbol;
@property (nonatomic, strong) UILabel *ramSubtextLabel;
@property (nonatomic, strong) PRMProgressBar *ramProgressBar;
@property (nonatomic, strong) PRMTelemetryRow *ramUsedRow;
@property (nonatomic, strong) PRMTelemetryRow *ramAvailRow;
@property (nonatomic, strong) PRMTelemetryRow *ramTotalRow;
@property (nonatomic, strong) PRMTelemetryRow *ramAllocRow;

// Card 5: Storage
@property (nonatomic, strong) PRMCardView *storageCard;
@property (nonatomic, strong) UIScrollView *volumesScrollView;
@property (nonatomic, strong) UILabel *vol0HeaderLabel;
@property (nonatomic, strong) PRMProgressBar *vol0Bar;
@property (nonatomic, strong) UILabel *vol0SubtextLabel;
@property (nonatomic, strong) UILabel *vol1HeaderLabel;
@property (nonatomic, strong) PRMProgressBar *vol1Bar;
@property (nonatomic, strong) UILabel *vol1SubtextLabel;
@property (nonatomic, strong) UILabel *vol2HeaderLabel;
@property (nonatomic, strong) PRMProgressBar *vol2Bar;
@property (nonatomic, strong) UILabel *vol2SubtextLabel;
@property (nonatomic, strong) UILabel *extraVolumesLabel;
@property (nonatomic, strong) UIView *storageDivider;
@property (nonatomic, strong) PRMTelemetryRow *ioReadRow;
@property (nonatomic, strong) PRMTelemetryRow *ioWriteRow;
@property (nonatomic, strong) PRMTelemetryRow *ioStatusRow;

// Card 6: Network & System
@property (nonatomic, strong) PRMCardView *networkCard;
@property (nonatomic, strong) PRMTelemetryRow *netDownRow;
@property (nonatomic, strong) PRMTelemetryRow *netUpRow;
@property (nonatomic, strong) PRMTelemetryRow *netAdapterRow;
@property (nonatomic, strong) UIView *networkDivider;
@property (nonatomic, strong) PRMTelemetryRow *sysHostRow;
@property (nonatomic, strong) PRMTelemetryRow *sysOsRow;
@property (nonatomic, strong) PRMTelemetryRow *sysUptimeRow;

@end

@implementation PRMDashboardViewController

- (void)viewDidLoad {
    [super viewDidLoad];

    // Background: Deep Abyss Navy (#080c16)
    self.view.opaque = YES;
    self.view.backgroundColor = [UIColor colorWithRed:8.0/255.0 green:12.0/255.0 blue:22.0/255.0 alpha:1.0];

    // 1. Header Bar
    self.headerView = [[PRMStatusHeaderView alloc] initWithFrame:CGRectZero];
    [self.view addSubview:self.headerView];

    // 2. Construct Cards
    [self constructCpuCard];
    [self constructNvidiaCard];
    [self constructFpsCard];
    [self constructMemoryCard];
    [self constructStorageCard];
    [self constructNetworkCard];

    // 3. Connect Telemetry Client
    self.telemetryClient = [PRMTelemetryClient defaultClient];
    self.telemetryClient.delegate = self;
    [self.telemetryClient startPolling];
}

#pragma mark - Card Construction (Cached Subviews)

- (void)constructCpuCard {
    self.cpuCard = [[PRMCardView alloc] initWithTitle:@"CPU Compute" subtitle:@"Processor" badge:@"Cores"];
    [self.view addSubview:self.cpuCard];
    UIView *content = self.cpuCard.contentContainerView;
    UIColor *cardBg = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

    self.cpuPercentLabel = [[UILabel alloc] init];
    self.cpuPercentLabel.opaque = YES;
    self.cpuPercentLabel.backgroundColor = cardBg;
    self.cpuPercentLabel.text = @"--";
    self.cpuPercentLabel.textColor = [UIColor whiteColor];
    self.cpuPercentLabel.font = [UIFont boldSystemFontOfSize:40.0];
    [content addSubview:self.cpuPercentLabel];

    self.cpuPercentSymbol = [[UILabel alloc] init];
    self.cpuPercentSymbol.opaque = YES;
    self.cpuPercentSymbol.backgroundColor = cardBg;
    self.cpuPercentSymbol.text = @"%";
    self.cpuPercentSymbol.textColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
    self.cpuPercentSymbol.font = [UIFont boldSystemFontOfSize:18.0];
    [content addSubview:self.cpuPercentSymbol];

    self.cpuSubtextLabel = [[UILabel alloc] init];
    self.cpuSubtextLabel.opaque = YES;
    self.cpuSubtextLabel.backgroundColor = cardBg;
    self.cpuSubtextLabel.text = @"TOTAL UTILIZATION";
    self.cpuSubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.cpuSubtextLabel.font = [UIFont boldSystemFontOfSize:10.0];
    [content addSubview:self.cpuSubtextLabel];

    self.cpuProgressBar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.cpuProgressBar.useThresholdColors = YES;
    self.cpuProgressBar.fillColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
    [content addSubview:self.cpuProgressBar];

    self.cpuFreqRow = [[PRMTelemetryRow alloc] initWithTitle:@"Clock Frequency"];
    [content addSubview:self.cpuFreqRow];

    self.cpuTopologyRow = [[PRMTelemetryRow alloc] initWithTitle:@"Topology"];
    [content addSubview:self.cpuTopologyRow];

    // Core Matrix: Pre-allocate 16 mini-bars
    self.coreMatrixContainer = [[UIView alloc] init];
    [content addSubview:self.coreMatrixContainer];

    self.coreBarTracks = [NSMutableArray array];
    self.coreBarFills = [NSMutableArray array];
    for (int i = 0; i < 16; i++) {
        UIView *track = [[UIView alloc] init];
        track.opaque = YES;
        track.backgroundColor = [UIColor colorWithRed:22.0/255.0 green:34.0/255.0 blue:56.0/255.0 alpha:1.0];
        track.layer.cornerRadius = 2.0;
        track.layer.masksToBounds = NO;
        if (i >= 12) {
            track.hidden = YES;
        }
        [self.coreMatrixContainer addSubview:track];
        [self.coreBarTracks addObject:track];

        UIView *fill = [[UIView alloc] init];
        fill.opaque = YES;
        fill.backgroundColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
        fill.layer.cornerRadius = 2.0;
        [track addSubview:fill];
        [self.coreBarFills addObject:fill];
    }
}

- (void)constructNvidiaCard {
    self.nvidiaCard = [[PRMCardView alloc] initWithTitle:@"Primary GPU" subtitle:@"NVIDIA GeForce" badge:@"dGPU"];
    [self.view addSubview:self.nvidiaCard];
    UIView *content = self.nvidiaCard.contentContainerView;
    UIColor *cardBg = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

    self.gpuNvidiaPercentLabel = [[UILabel alloc] init];
    self.gpuNvidiaPercentLabel.opaque = YES;
    self.gpuNvidiaPercentLabel.backgroundColor = cardBg;
    self.gpuNvidiaPercentLabel.text = @"--";
    self.gpuNvidiaPercentLabel.textColor = [UIColor whiteColor];
    self.gpuNvidiaPercentLabel.font = [UIFont boldSystemFontOfSize:40.0];
    [content addSubview:self.gpuNvidiaPercentLabel];

    self.gpuNvidiaPercentSymbol = [[UILabel alloc] init];
    self.gpuNvidiaPercentSymbol.opaque = YES;
    self.gpuNvidiaPercentSymbol.backgroundColor = cardBg;
    self.gpuNvidiaPercentSymbol.text = @"%";
    self.gpuNvidiaPercentSymbol.textColor = [UIColor colorWithRed:168.0/255.0 green:85.0/255.0 blue:247.0/255.0 alpha:1.0]; // Purple
    self.gpuNvidiaPercentSymbol.font = [UIFont boldSystemFontOfSize:18.0];
    [content addSubview:self.gpuNvidiaPercentSymbol];

    self.gpuNvidiaSubtextLabel = [[UILabel alloc] init];
    self.gpuNvidiaSubtextLabel.opaque = YES;
    self.gpuNvidiaSubtextLabel.backgroundColor = cardBg;
    self.gpuNvidiaSubtextLabel.text = @"CORE UTILIZATION";
    self.gpuNvidiaSubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.gpuNvidiaSubtextLabel.font = [UIFont boldSystemFontOfSize:10.0];
    [content addSubview:self.gpuNvidiaSubtextLabel];

    self.gpuNvidiaNotDetectedLabel = [[UILabel alloc] init];
    self.gpuNvidiaNotDetectedLabel.opaque = YES;
    self.gpuNvidiaNotDetectedLabel.backgroundColor = cardBg;
    self.gpuNvidiaNotDetectedLabel.text = @"NOT DETECTED";
    self.gpuNvidiaNotDetectedLabel.textColor = [UIColor colorWithRed:100.0/255.0 green:116.0/255.0 blue:139.0/255.0 alpha:1.0];
    self.gpuNvidiaNotDetectedLabel.font = [UIFont boldSystemFontOfSize:22.0];
    self.gpuNvidiaNotDetectedLabel.hidden = YES;
    [content addSubview:self.gpuNvidiaNotDetectedLabel];

    self.gpuNvidiaProgressBar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.gpuNvidiaProgressBar.useThresholdColors = YES;
    self.gpuNvidiaProgressBar.fillColor = [UIColor colorWithRed:168.0/255.0 green:85.0/255.0 blue:247.0/255.0 alpha:1.0];
    [content addSubview:self.gpuNvidiaProgressBar];

    // Rows: Clock, Power, Temp, VRAM, and VRAM Bar
    self.gpuNvidiaClockRow = [[PRMTelemetryRow alloc] initWithTitle:@"Graphics Clock"];
    [content addSubview:self.gpuNvidiaClockRow];

    self.gpuNvidiaPowerRow = [[PRMTelemetryRow alloc] initWithTitle:@"Power Draw"];
    [content addSubview:self.gpuNvidiaPowerRow];

    self.gpuNvidiaTempRow = [[PRMTelemetryRow alloc] initWithTitle:@"Core Temp"];
    [content addSubview:self.gpuNvidiaTempRow];

    self.gpuNvidiaVramRow = [[PRMTelemetryRow alloc] initWithTitle:@"Dedicated VRAM"];
    [content addSubview:self.gpuNvidiaVramRow];

    self.gpuNvidiaVramBar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.gpuNvidiaVramBar.fillColor = [UIColor colorWithRed:168.0/255.0 green:85.0/255.0 blue:247.0/255.0 alpha:1.0];
    [content addSubview:self.gpuNvidiaVramBar];
}

- (void)constructFpsCard {
    self.fpsCard = [[PRMCardView alloc] initWithTitle:@"Gaming & FPS" subtitle:@"Real-Time PresentMon" badge:@"ETW"];
    [self.view addSubview:self.fpsCard];
    UIView *content = self.fpsCard.contentContainerView;
    UIColor *cardBg = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

    self.fpsHeroLabel = [[UILabel alloc] init];
    self.fpsHeroLabel.opaque = YES;
    self.fpsHeroLabel.backgroundColor = cardBg;
    self.fpsHeroLabel.text = @"--";
    self.fpsHeroLabel.textColor = [UIColor colorWithRed:248.0/255.0 green:250.0/255.0 blue:252.0/255.0 alpha:1.0];
    self.fpsHeroLabel.font = [UIFont boldSystemFontOfSize:38.0];
    [content addSubview:self.fpsHeroLabel];

    self.fpsHeroUnit = [[UILabel alloc] init];
    self.fpsHeroUnit.opaque = YES;
    self.fpsHeroUnit.backgroundColor = cardBg;
    self.fpsHeroUnit.text = @"FPS";
    self.fpsHeroUnit.textColor = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0];
    self.fpsHeroUnit.font = [UIFont boldSystemFontOfSize:14.0];
    [content addSubview:self.fpsHeroUnit];

    self.fpsHeroSubtext = [[UILabel alloc] init];
    self.fpsHeroSubtext.opaque = YES;
    self.fpsHeroSubtext.backgroundColor = cardBg;
    self.fpsHeroSubtext.text = @"DESKTOP IDLE";
    self.fpsHeroSubtext.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.fpsHeroSubtext.font = [UIFont boldSystemFontOfSize:10.0];
    [content addSubview:self.fpsHeroSubtext];

    self.fpsProgressBar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.fpsProgressBar.useThresholdColors = NO;
    self.fpsProgressBar.fillColor = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0];
    [content addSubview:self.fpsProgressBar];

    self.fpsProcessRow = [[PRMTelemetryRow alloc] initWithTitle:@"Active Process"];
    [content addSubview:self.fpsProcessRow];

    self.fpsFrameTimeRow = [[PRMTelemetryRow alloc] initWithTitle:@"Frame Time"];
    [content addSubview:self.fpsFrameTimeRow];

    self.fpsApiRow = [[PRMTelemetryRow alloc] initWithTitle:@"Graphics API"];
    [content addSubview:self.fpsApiRow];

    self.fpsStatusRow = [[PRMTelemetryRow alloc] initWithTitle:@"ETW Session"];
    [content addSubview:self.fpsStatusRow];
}

- (void)constructMemoryCard {
    self.memoryCard = [[PRMCardView alloc] initWithTitle:@"System Memory" subtitle:@"RAM Pool" badge:@"DDR5"];
    [self.view addSubview:self.memoryCard];
    UIView *content = self.memoryCard.contentContainerView;
    UIColor *cardBg = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

    self.ramPercentLabel = [[UILabel alloc] init];
    self.ramPercentLabel.opaque = YES;
    self.ramPercentLabel.backgroundColor = cardBg;
    self.ramPercentLabel.text = @"--";
    self.ramPercentLabel.textColor = [UIColor whiteColor];
    self.ramPercentLabel.font = [UIFont boldSystemFontOfSize:40.0];
    [content addSubview:self.ramPercentLabel];

    self.ramPercentSymbol = [[UILabel alloc] init];
    self.ramPercentSymbol.opaque = YES;
    self.ramPercentSymbol.backgroundColor = cardBg;
    self.ramPercentSymbol.text = @"%";
    self.ramPercentSymbol.textColor = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0]; // Green
    self.ramPercentSymbol.font = [UIFont boldSystemFontOfSize:18.0];
    [content addSubview:self.ramPercentSymbol];

    self.ramSubtextLabel = [[UILabel alloc] init];
    self.ramSubtextLabel.opaque = YES;
    self.ramSubtextLabel.backgroundColor = cardBg;
    self.ramSubtextLabel.text = @"PHYSICAL RAM LOAD";
    self.ramSubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.ramSubtextLabel.font = [UIFont boldSystemFontOfSize:10.0];
    [content addSubview:self.ramSubtextLabel];

    self.ramProgressBar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.ramProgressBar.useThresholdColors = YES;
    self.ramProgressBar.fillColor = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0];
    [content addSubview:self.ramProgressBar];

    self.ramUsedRow = [[PRMTelemetryRow alloc] initWithTitle:@"Used Memory"];
    [content addSubview:self.ramUsedRow];

    self.ramAvailRow = [[PRMTelemetryRow alloc] initWithTitle:@"Available Memory"];
    [content addSubview:self.ramAvailRow];

    self.ramTotalRow = [[PRMTelemetryRow alloc] initWithTitle:@"Total Installed"];
    [content addSubview:self.ramTotalRow];

    self.ramAllocRow = [[PRMTelemetryRow alloc] initWithTitle:@"Allocation"];
    [content addSubview:self.ramAllocRow];
}

- (void)constructStorageCard {
    self.storageCard = [[PRMCardView alloc] initWithTitle:@"Storage Subsystem" subtitle:@"Logical Volumes" badge:@"Fixed"];
    [self.view addSubview:self.storageCard];
    UIView *content = self.storageCard.contentContainerView;
    UIColor *cardBg = [UIColor colorWithRed:13.0/255.0 green:21.0/255.0 blue:38.0/255.0 alpha:1.0];

    // Scroll view for dynamic volumes (sits above the fixed divider and I/O rows)
    self.volumesScrollView = [[UIScrollView alloc] initWithFrame:CGRectZero];
    self.volumesScrollView.opaque = YES;
    self.volumesScrollView.backgroundColor = cardBg;
    self.volumesScrollView.showsVerticalScrollIndicator = YES;
    self.volumesScrollView.showsHorizontalScrollIndicator = NO;
    self.volumesScrollView.alwaysBounceVertical = NO;
    if ([self.volumesScrollView respondsToSelector:@selector(setIndicatorStyle:)]) {
        self.volumesScrollView.indicatorStyle = UIScrollViewIndicatorStyleWhite;
    }
    [content addSubview:self.volumesScrollView];

    // Volume 0 (inside volumesScrollView)
    self.vol0HeaderLabel = [[UILabel alloc] init];
    self.vol0HeaderLabel.opaque = YES;
    self.vol0HeaderLabel.backgroundColor = cardBg;
    self.vol0HeaderLabel.text = @"Drive C: --";
    self.vol0HeaderLabel.textColor = [UIColor colorWithRed:226.0/255.0 green:232.0/255.0 blue:240.0/255.0 alpha:1.0];
    self.vol0HeaderLabel.font = [UIFont boldSystemFontOfSize:12.0];
    [self.volumesScrollView addSubview:self.vol0HeaderLabel];

    self.vol0Bar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.vol0Bar.useThresholdColors = YES;
    self.vol0Bar.fillColor = [UIColor colorWithRed:249.0/255.0 green:115.0/255.0 blue:22.0/255.0 alpha:1.0];
    [self.volumesScrollView addSubview:self.vol0Bar];

    self.vol0SubtextLabel = [[UILabel alloc] init];
    self.vol0SubtextLabel.opaque = YES;
    self.vol0SubtextLabel.backgroundColor = cardBg;
    self.vol0SubtextLabel.text = @"-- free";
    self.vol0SubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.vol0SubtextLabel.font = [UIFont systemFontOfSize:11.0];
    [self.volumesScrollView addSubview:self.vol0SubtextLabel];

    // Volume 1 (inside volumesScrollView)
    self.vol1HeaderLabel = [[UILabel alloc] init];
    self.vol1HeaderLabel.opaque = YES;
    self.vol1HeaderLabel.backgroundColor = cardBg;
    self.vol1HeaderLabel.text = @"Drive D: --";
    self.vol1HeaderLabel.textColor = [UIColor colorWithRed:226.0/255.0 green:232.0/255.0 blue:240.0/255.0 alpha:1.0];
    self.vol1HeaderLabel.font = [UIFont boldSystemFontOfSize:12.0];
    [self.volumesScrollView addSubview:self.vol1HeaderLabel];

    self.vol1Bar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.vol1Bar.useThresholdColors = YES;
    self.vol1Bar.fillColor = [UIColor colorWithRed:249.0/255.0 green:115.0/255.0 blue:22.0/255.0 alpha:1.0];
    [self.volumesScrollView addSubview:self.vol1Bar];

    self.vol1SubtextLabel = [[UILabel alloc] init];
    self.vol1SubtextLabel.opaque = YES;
    self.vol1SubtextLabel.backgroundColor = cardBg;
    self.vol1SubtextLabel.text = @"-- free";
    self.vol1SubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.vol1SubtextLabel.font = [UIFont systemFontOfSize:11.0];
    [self.volumesScrollView addSubview:self.vol1SubtextLabel];

    // Volume 2 (Dynamic Drive, inside volumesScrollView)
    self.vol2HeaderLabel = [[UILabel alloc] init];
    self.vol2HeaderLabel.opaque = YES;
    self.vol2HeaderLabel.backgroundColor = cardBg;
    self.vol2HeaderLabel.text = @"Drive E: --";
    self.vol2HeaderLabel.textColor = [UIColor colorWithRed:226.0/255.0 green:232.0/255.0 blue:240.0/255.0 alpha:1.0];
    self.vol2HeaderLabel.font = [UIFont boldSystemFontOfSize:12.0];
    self.vol2HeaderLabel.hidden = YES;
    [self.volumesScrollView addSubview:self.vol2HeaderLabel];

    self.vol2Bar = [[PRMProgressBar alloc] initWithFrame:CGRectZero];
    self.vol2Bar.useThresholdColors = YES;
    self.vol2Bar.fillColor = [UIColor colorWithRed:249.0/255.0 green:115.0/255.0 blue:22.0/255.0 alpha:1.0];
    self.vol2Bar.hidden = YES;
    [self.volumesScrollView addSubview:self.vol2Bar];

    self.vol2SubtextLabel = [[UILabel alloc] init];
    self.vol2SubtextLabel.opaque = YES;
    self.vol2SubtextLabel.backgroundColor = cardBg;
    self.vol2SubtextLabel.text = @"-- free";
    self.vol2SubtextLabel.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
    self.vol2SubtextLabel.font = [UIFont systemFontOfSize:11.0];
    self.vol2SubtextLabel.hidden = YES;
    [self.volumesScrollView addSubview:self.vol2SubtextLabel];

    // Extra Volumes Indicator (inside volumesScrollView)
    self.extraVolumesLabel = [[UILabel alloc] init];
    self.extraVolumesLabel.opaque = YES;
    self.extraVolumesLabel.backgroundColor = cardBg;
    self.extraVolumesLabel.textColor = [UIColor colorWithRed:148.0/255.0 green:163.0/255.0 blue:184.0/255.0 alpha:1.0];
    self.extraVolumesLabel.font = [UIFont boldSystemFontOfSize:11.0];
    self.extraVolumesLabel.lineBreakMode = NSLineBreakByTruncatingTail;
    self.extraVolumesLabel.hidden = YES;
    [self.volumesScrollView addSubview:self.extraVolumesLabel];

    // Fixed / Anchored bottom views (inside content, OUTSIDE scroll view)
    self.storageDivider = [[UIView alloc] init];
    self.storageDivider.backgroundColor = [UIColor colorWithRed:30.0/255.0 green:48.0/255.0 blue:80.0/255.0 alpha:0.40];
    [content addSubview:self.storageDivider];

    self.ioReadRow = [[PRMTelemetryRow alloc] initWithTitle:@"Read Rate"];
    [content addSubview:self.ioReadRow];

    self.ioWriteRow = [[PRMTelemetryRow alloc] initWithTitle:@"Write Rate"];
    [content addSubview:self.ioWriteRow];

    self.ioStatusRow = [[PRMTelemetryRow alloc] initWithTitle:@"I/O Activity"];
    [content addSubview:self.ioStatusRow];
}

- (void)constructNetworkCard {
    self.networkCard = [[PRMCardView alloc] initWithTitle:@"Network & System" subtitle:@"Diagnostics" badge:@"Tethered"];
    [self.view addSubview:self.networkCard];
    UIView *content = self.networkCard.contentContainerView;

    self.netDownRow = [[PRMTelemetryRow alloc] initWithTitle:@"Download Rate"];
    self.netDownRow.valueLabel.textColor = [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0]; // Cyan
    [content addSubview:self.netDownRow];

    self.netUpRow = [[PRMTelemetryRow alloc] initWithTitle:@"Upload Rate"];
    self.netUpRow.valueLabel.textColor = [UIColor colorWithRed:147.0/255.0 green:197.0/255.0 blue:253.0/255.0 alpha:1.0]; // Light blue
    [content addSubview:self.netUpRow];

    self.netAdapterRow = [[PRMTelemetryRow alloc] initWithTitle:@"Interface"];
    [content addSubview:self.netAdapterRow];

    self.networkDivider = [[UIView alloc] init];
    self.networkDivider.backgroundColor = [UIColor colorWithRed:30.0/255.0 green:48.0/255.0 blue:80.0/255.0 alpha:0.40];
    [content addSubview:self.networkDivider];

    self.sysHostRow = [[PRMTelemetryRow alloc] initWithTitle:@"Host Device"];
    [content addSubview:self.sysHostRow];

    self.sysOsRow = [[PRMTelemetryRow alloc] initWithTitle:@"OS Platform"];
    [content addSubview:self.sysOsRow];

    self.sysUptimeRow = [[PRMTelemetryRow alloc] initWithTitle:@"System Uptime"];
    [content addSubview:self.sysUptimeRow];
}

#pragma mark - Layout

- (void)viewWillLayoutSubviews {
    [super viewWillLayoutSubviews];

    // Total landscape resolution: 1024 × 768
    CGFloat screenW = self.view.bounds.size.width > 0 ? self.view.bounds.size.width : 1024.0;
    CGFloat marginX = 16.0;
    CGFloat cardGapX = 16.0;
    CGFloat cardW = 320.0; // 16 + 320 + 16 + 320 + 16 + 320 + 16 = 1024

    CGFloat headerY = 12.0;
    CGFloat headerH = 44.0;
    self.headerView.frame = CGRectMake(marginX, headerY, screenW - (marginX * 2), headerH);

    CGFloat row0Y = 66.0;
    CGFloat cardH = 336.0;
    CGFloat cardGapY = 13.0;
    CGFloat row1Y = row0Y + cardH + cardGapY; // 66 + 336 + 13 = 415; 415 + 336 = 751; 17pt bottom margin

    CGFloat col0X = marginX;
    CGFloat col1X = col0X + cardW + cardGapX;
    CGFloat col2X = col1X + cardW + cardGapX;

    // Row 0: CPU Compute (320pt), Primary GPU (320pt), Gaming & FPS (320pt)
    self.cpuCard.frame = CGRectMake(col0X, row0Y, cardW, cardH);
    self.nvidiaCard.frame = CGRectMake(col1X, row0Y, cardW, cardH);
    self.fpsCard.frame = CGRectMake(col2X, row0Y, cardW, cardH);

    // Row 1: Memory (320pt), Storage (320pt), Network & System (320pt)
    self.memoryCard.frame = CGRectMake(col0X, row1Y, cardW, cardH);
    self.storageCard.frame = CGRectMake(col1X, row1Y, cardW, cardH);
    self.networkCard.frame = CGRectMake(col2X, row1Y, cardW, cardH);

    // Layout inside each card's content container
    [self layoutCardSubviews];
}

- (void)layoutCardSubviews {
    CGFloat cW = 292.0; // cardW (320) - padding (28)

    // Layout helper for big percentage top section
    void (^layoutTopSection)(UILabel *, UILabel *, UILabel *, PRMProgressBar *) = ^(UILabel *pct, UILabel *sym, UILabel *sub, PRMProgressBar *bar) {
        pct.frame = CGRectMake(0, 0, 72.0, 42.0);
        sym.frame = CGRectMake(72.0, 14.0, 20.0, 24.0);
        sub.frame = CGRectMake(98.0, 17.0, cW - 98.0, 18.0);
        bar.frame = CGRectMake(0, 48.0, cW, 7.0);
    };

    // Card 1: CPU
    layoutTopSection(self.cpuPercentLabel, self.cpuPercentSymbol, self.cpuSubtextLabel, self.cpuProgressBar);
    self.cpuFreqRow.frame = CGRectMake(0, 68.0, cW, 24.0);
    self.cpuTopologyRow.frame = CGRectMake(0, 96.0, cW, 24.0);

    // CPU Core Matrix (at bottom of CPU card)
    CGFloat matrixY = 132.0;
    CGFloat matrixH = 125.0;
    self.coreMatrixContainer.frame = CGRectMake(0, matrixY, cW, matrixH);

    // CPU Core Matrix: 12 logical processors arranged in 2 rows of 6 bars
    // Each column corresponds to one physical core:
    // Top row (row 0) = first logical thread (col = i / 2, row = 0)
    // Bottom row (row 1) = SMT sibling thread (col = i / 2, row = 1)
    CGFloat barW = 36.0;
    CGFloat barH = 50.0;
    CGFloat startX = 8.0;
    CGFloat gapX = 12.0;
    CGFloat startY = 5.0;
    CGFloat gapY = 10.0;

    for (int i = 0; i < 16; i++) {
        UIView *track = self.coreBarTracks[i];
        UIView *fill = self.coreBarFills[i];
        if (i < 12) {
            int col = i / 2;
            int row = i % 2;
            CGFloat x = startX + col * (barW + gapX);
            CGFloat y = startY + row * (barH + gapY);
            track.frame = CGRectMake(x, y, barW, barH);
            CGFloat fillH = fill.frame.size.height;
            fill.frame = CGRectMake(0, barH - fillH, barW, fillH);
        } else {
            track.frame = CGRectZero;
            track.hidden = YES;
            fill.frame = CGRectZero;
        }
    }

    // Card 2: Primary GPU
    layoutTopSection(self.gpuNvidiaPercentLabel, self.gpuNvidiaPercentSymbol, self.gpuNvidiaSubtextLabel, self.gpuNvidiaProgressBar);
    self.gpuNvidiaNotDetectedLabel.frame = CGRectMake(0, 70.0, cW, 40.0);
    self.gpuNvidiaClockRow.frame = CGRectMake(0, 68.0, cW, 24.0);
    self.gpuNvidiaPowerRow.frame = CGRectMake(0, 94.0, cW, 24.0);
    self.gpuNvidiaTempRow.frame = CGRectMake(0, 120.0, cW, 24.0);
    self.gpuNvidiaVramRow.frame = CGRectMake(0, 146.0, cW, 24.0);
    self.gpuNvidiaVramBar.frame = CGRectMake(0, 172.0, cW, 6.0);

    // Card 3: Gaming & FPS
    self.fpsHeroLabel.frame = CGRectMake(0, 0, 90.0, 42.0);
    self.fpsHeroUnit.frame = CGRectMake(92.0, 14.0, 40.0, 24.0);
    self.fpsHeroSubtext.frame = CGRectMake(136.0, 17.0, cW - 136.0, 18.0);
    self.fpsProgressBar.frame = CGRectMake(0, 48.0, cW, 7.0);
    self.fpsProcessRow.frame = CGRectMake(0, 68.0, cW, 24.0);
    self.fpsFrameTimeRow.frame = CGRectMake(0, 94.0, cW, 24.0);
    self.fpsApiRow.frame = CGRectMake(0, 120.0, cW, 24.0);
    self.fpsStatusRow.frame = CGRectMake(0, 146.0, cW, 24.0);

    // Card 3: Memory
    layoutTopSection(self.ramPercentLabel, self.ramPercentSymbol, self.ramSubtextLabel, self.ramProgressBar);
    self.ramUsedRow.frame = CGRectMake(0, 68.0, cW, 24.0);
    self.ramAvailRow.frame = CGRectMake(0, 94.0, cW, 24.0);
    self.ramTotalRow.frame = CGRectMake(0, 120.0, cW, 24.0);
    self.ramAllocRow.frame = CGRectMake(0, 146.0, cW, 24.0);

    // Card 5: Storage (Volumes inside volumesScrollView, fixed I/O rows anchored at bottom)
    CGFloat storageH = self.storageCard.contentContainerView.bounds.size.height;
    if (storageH <= 0) storageH = 280.0;
    CGFloat divY = storageH - 84.0;

    self.volumesScrollView.frame = CGRectMake(0, 0, cW, divY - 4.0);

    self.vol0HeaderLabel.frame = CGRectMake(0, 2.0, cW, 18.0);
    self.vol0Bar.frame = CGRectMake(0, 22.0, cW, 6.0);
    self.vol0SubtextLabel.frame = CGRectMake(0, 30.0, cW, 16.0);

    self.vol1HeaderLabel.frame = CGRectMake(0, 50.0, cW, 18.0);
    self.vol1Bar.frame = CGRectMake(0, 70.0, cW, 6.0);
    self.vol1SubtextLabel.frame = CGRectMake(0, 78.0, cW, 16.0);

    self.vol2HeaderLabel.frame = CGRectMake(0, 98.0, cW, 18.0);
    self.vol2Bar.frame = CGRectMake(0, 118.0, cW, 6.0);
    self.vol2SubtextLabel.frame = CGRectMake(0, 126.0, cW, 16.0);
    self.vol2HeaderLabel.hidden = YES;
    self.vol2Bar.hidden = YES;
    self.vol2SubtextLabel.hidden = YES;

    self.extraVolumesLabel.frame = CGRectMake(0, 146.0, cW, 18.0);
    self.extraVolumesLabel.hidden = YES;

    self.volumesScrollView.contentSize = CGSizeMake(cW, 98.0);

    self.storageDivider.frame = CGRectMake(0, divY, cW, 1.0);
    self.ioReadRow.frame = CGRectMake(0, divY + 8.0, cW, 22.0);
    self.ioWriteRow.frame = CGRectMake(0, divY + 32.0, cW, 22.0);
    self.ioStatusRow.frame = CGRectMake(0, divY + 56.0, cW, 22.0);

    // Card 6: Network & System
    self.netDownRow.frame = CGRectMake(0, 4.0, cW, 22.0);
    self.netUpRow.frame = CGRectMake(0, 28.0, cW, 22.0);
    self.netAdapterRow.frame = CGRectMake(0, 52.0, cW, 22.0);

    self.networkDivider.frame = CGRectMake(0, 82.0, cW, 1.0);
    self.sysHostRow.frame = CGRectMake(0, 90.0, cW, 22.0);
    self.sysOsRow.frame = CGRectMake(0, 114.0, cW, 22.0);
    self.sysUptimeRow.frame = CGRectMake(0, 138.0, cW, 22.0);
}

#pragma mark - PRMTelemetryClientDelegate

- (void)telemetryClient:(PRMTelemetryClient *)client didChangeConnectionState:(PRMConnectionState)state {
    [self.headerView updateWithConnectionState:state
                                     sequence:client.lastSequence
                                    timestamp:nil];
}

- (void)telemetryClient:(PRMTelemetryClient *)client didReceiveSnapshot:(PRMTelemetrySnapshot *)snapshot {
    // 1. Update Header
    [self.headerView updateWithConnectionState:PRMConnectionStateLive
                                     sequence:snapshot.sequence
                                    timestamp:snapshot.generatedAt];
    [self.headerView setSystemHost:snapshot.system.hostname osName:snapshot.system.os];

    // 2. Update CPU Card
    [self updateCpuWithSnapshot:snapshot.cpu system:snapshot.system];

    // 3. Update GPU Cards
    [self updateGpusWithSnapshot:snapshot.gpus];

    // 4. Update Gaming & FPS Card
    [self updateFpsWithSnapshot:snapshot.fps];

    // 5. Update Memory Card
    [self updateMemoryWithSnapshot:snapshot.memory];

    // 6. Update Storage Card
    [self updateStorageWithSnapshot:snapshot.storage];

    // 7. Update Network & System Card
    [self updateNetworkWithSnapshot:snapshot.network system:snapshot.system];
}

- (void)telemetryClient:(PRMTelemetryClient *)client didFailWithError:(NSError *)error {
    // State machine updates header badge automatically; nothing needs tearing down
}

#pragma mark - Telemetry Rendering Logic

- (void)updateCpuWithSnapshot:(nullable PRMCpuSnapshot *)cpu system:(nullable PRMSystemSnapshot *)system {
    if (system.cpuName.length > 0) {
        [self.cpuCard setSubtitle:system.cpuName];
    }

    if (cpu && [cpu.status isEqualToString:@"ok"]) {
        // Usage percent
        if (cpu.usagePercent) {
            double usage = [cpu.usagePercent doubleValue];
            NSString *targetUsage = [NSString stringWithFormat:@"%.0f", usage];
            if (![self.cpuPercentLabel.text isEqualToString:targetUsage]) {
                self.cpuPercentLabel.text = targetUsage;
            }
            [self.cpuProgressBar setProgress:(usage / 100.0) animated:YES];
        } else {
            if (![self.cpuPercentLabel.text isEqualToString:@"--"]) {
                self.cpuPercentLabel.text = @"--";
            }
            [self.cpuProgressBar setProgress:0.0 animated:NO];
        }

        // Frequency
        if (cpu.frequencyMhz) {
            double ghz = [cpu.frequencyMhz doubleValue] / 1000.0;
            [self.cpuFreqRow setValueText:[NSString stringWithFormat:@"%.2f GHz", ghz] isAvailable:YES];
        } else {
            [self.cpuFreqRow setValueText:nil isAvailable:NO];
        }

        // Topology
        NSString *phys = cpu.coresPhysical ? [cpu.coresPhysical stringValue] : @"--";
        NSString *log = cpu.coresLogical ? [cpu.coresLogical stringValue] : @"--";
        [self.cpuTopologyRow setValueText:[NSString stringWithFormat:@"%@ Phys / %@ Log", phys, log] isAvailable:YES];
        [self.cpuCard setBadge:[NSString stringWithFormat:@"%@C / %@T", phys, log]];

        // Core Matrix mini bars (2 rows of 6 bars for 12 logical processors)
        NSArray<NSNumber *> *cores = cpu.perCorePercent;
        NSUInteger coreCount = cores.count;
        CGFloat barW = 36.0;
        CGFloat maxH = 50.0;
        for (NSUInteger i = 0; i < 16; i++) {
            UIView *track = self.coreBarTracks[i];
            UIView *fill = self.coreBarFills[i];
            if (i < coreCount && i < 12) {
                if (track.hidden) track.hidden = NO;
                double pct = [cores[i] doubleValue];
                if (pct < 0.0) pct = 0.0;
                if (pct > 100.0) pct = 100.0;
                CGFloat barH = round(maxH * (pct / 100.0));
                CGRect targetFrame = CGRectMake(0, maxH - barH, barW, barH);
                if (!CGRectEqualToRect(fill.frame, targetFrame)) {
                    fill.frame = targetFrame;
                }
                UIColor *targetColor = (pct >= 85.0) ?
                    [UIColor colorWithRed:239.0/255.0 green:68.0/255.0 blue:68.0/255.0 alpha:1.0] :
                    [UIColor colorWithRed:0.0 green:210.0/255.0 blue:255.0/255.0 alpha:1.0];
                if (fill.backgroundColor != targetColor) {
                    fill.backgroundColor = targetColor;
                }
            } else {
                if (!track.hidden) track.hidden = YES;
                if (fill.frame.size.height > 0) {
                    fill.frame = CGRectMake(0, maxH, barW, 0);
                }
            }
        }
    } else {
        if (![self.cpuPercentLabel.text isEqualToString:@"--"]) {
            self.cpuPercentLabel.text = @"--";
        }
        [self.cpuProgressBar setProgress:0.0 animated:NO];
        [self.cpuFreqRow setValueText:nil isAvailable:NO];
        [self.cpuTopologyRow setValueText:nil isAvailable:NO];
        CGFloat barW = 36.0;
        CGFloat maxH = 50.0;
        for (NSUInteger i = 0; i < 16; i++) {
            if (!self.coreBarTracks[i].hidden) self.coreBarTracks[i].hidden = YES;
            if (self.coreBarFills[i].frame.size.height > 0) {
                self.coreBarFills[i].frame = CGRectMake(0, maxH, barW, 0);
            }
        }
    }
}

- (void)updateGpusWithSnapshot:(nullable PRMGpusSnapshot *)gpus {
    // Primary / Dedicated GPU
    PRMGpuDeviceSnapshot *nvidia = gpus.nvidiaDevice;
    if (nvidia) {
        [self.nvidiaCard setSubtitle:nvidia.name];
        if (!self.gpuNvidiaNotDetectedLabel.hidden) self.gpuNvidiaNotDetectedLabel.hidden = YES;
        if (self.gpuNvidiaPercentLabel.hidden) self.gpuNvidiaPercentLabel.hidden = NO;
        if (self.gpuNvidiaPercentSymbol.hidden) self.gpuNvidiaPercentSymbol.hidden = NO;
        if (self.gpuNvidiaProgressBar.hidden) self.gpuNvidiaProgressBar.hidden = NO;
        if (self.gpuNvidiaClockRow.hidden) self.gpuNvidiaClockRow.hidden = NO;
        if (self.gpuNvidiaPowerRow.hidden) self.gpuNvidiaPowerRow.hidden = NO;
        if (self.gpuNvidiaTempRow.hidden) self.gpuNvidiaTempRow.hidden = NO;
        if (self.gpuNvidiaVramRow.hidden) self.gpuNvidiaVramRow.hidden = NO;
        if (self.gpuNvidiaVramBar.hidden) self.gpuNvidiaVramBar.hidden = NO;

        if (nvidia.utilizationAvailable && nvidia.utilizationPercent) {
            double util = [nvidia.utilizationPercent doubleValue];
            NSString *targetStr = [NSString stringWithFormat:@"%.0f", util];
            if (![self.gpuNvidiaPercentLabel.text isEqualToString:targetStr]) {
                self.gpuNvidiaPercentLabel.text = targetStr;
            }
            [self.gpuNvidiaProgressBar setProgress:(util / 100.0) animated:YES];
        } else {
            if (![self.gpuNvidiaPercentLabel.text isEqualToString:@"--"]) {
                self.gpuNvidiaPercentLabel.text = @"--";
            }
            [self.gpuNvidiaProgressBar setProgress:0.0 animated:NO];
        }

        if (nvidia.graphicsClockAvailable && nvidia.graphicsClockMhz) {
            [self.gpuNvidiaClockRow setValueText:[NSString stringWithFormat:@"%@ MHz", nvidia.graphicsClockMhz] isAvailable:YES];
        } else {
            [self.gpuNvidiaClockRow setValueText:nil isAvailable:NO];
        }

        if (nvidia.powerAvailable && nvidia.powerWatts) {
            [self.gpuNvidiaPowerRow setValueText:[NSString stringWithFormat:@"%.1f W", [nvidia.powerWatts doubleValue]] isAvailable:YES];
        } else {
            [self.gpuNvidiaPowerRow setValueText:nil isAvailable:NO];
        }

        if (nvidia.temperatureAvailable && nvidia.temperatureC) {
            [self.gpuNvidiaTempRow setValueText:[NSString stringWithFormat:@"%.1f °C", [nvidia.temperatureC doubleValue]] isAvailable:YES];
        } else {
            [self.gpuNvidiaTempRow setValueText:nil isAvailable:NO];
        }

        if (nvidia.vramAvailable) {
            double usedGB = (double)nvidia.vramUsedBytes / 1073741824.0;
            double totGB = (double)nvidia.vramTotalBytes / 1073741824.0;
            double pct = (totGB > 0) ? (usedGB / totGB) : 0.0;
            [self.gpuNvidiaVramRow setValueText:[NSString stringWithFormat:@"%.1f / %.1f GB", usedGB, totGB] isAvailable:YES];
            [self.gpuNvidiaVramBar setProgress:pct animated:YES];
        } else {
            [self.gpuNvidiaVramRow setValueText:nil isAvailable:NO];
            [self.gpuNvidiaVramBar setProgress:0.0 animated:NO];
        }
    } else {
        [self.nvidiaCard setSubtitle:@"No Dedicated GPU Found"];
        if (self.gpuNvidiaNotDetectedLabel.hidden) self.gpuNvidiaNotDetectedLabel.hidden = NO;
        if (!self.gpuNvidiaPercentLabel.hidden) self.gpuNvidiaPercentLabel.hidden = YES;
        if (!self.gpuNvidiaPercentSymbol.hidden) self.gpuNvidiaPercentSymbol.hidden = YES;
        if (!self.gpuNvidiaProgressBar.hidden) self.gpuNvidiaProgressBar.hidden = YES;
        if (!self.gpuNvidiaClockRow.hidden) self.gpuNvidiaClockRow.hidden = YES;
        if (!self.gpuNvidiaPowerRow.hidden) self.gpuNvidiaPowerRow.hidden = YES;
        if (!self.gpuNvidiaTempRow.hidden) self.gpuNvidiaTempRow.hidden = YES;
        if (!self.gpuNvidiaVramRow.hidden) self.gpuNvidiaVramRow.hidden = YES;
        if (!self.gpuNvidiaVramBar.hidden) self.gpuNvidiaVramBar.hidden = YES;
    }
}

- (void)updateFpsWithSnapshot:(nullable PRMFpsSnapshot *)fps {
    if (fps && [fps.status isEqualToString:@"ok"]) {
        if (fps.isPresenting && fps.fps) {
            double val = [fps.fps doubleValue];
            NSString *targetFps = [NSString stringWithFormat:@"%.0f", val];
            if (![self.fpsHeroLabel.text isEqualToString:targetFps]) {
                self.fpsHeroLabel.text = targetFps;
            }
            if (![self.fpsHeroSubtext.text isEqualToString:@"ACTIVE IN-GAME"]) {
                self.fpsHeroSubtext.text = @"ACTIVE IN-GAME";
                self.fpsHeroSubtext.textColor = [UIColor colorWithRed:16.0/255.0 green:185.0/255.0 blue:129.0/255.0 alpha:1.0];
            }
            [self.fpsCard setBadge:@"LIVE"];

            double progress = val / 144.0;
            if (progress > 1.0) progress = 1.0;
            if (progress < 0.0) progress = 0.0;
            [self.fpsProgressBar setProgress:progress animated:YES];

            [self.fpsProcessRow setValueText:fps.activeProcess ?: @"Active Game" isAvailable:YES];

            if (fps.frameTimeMs) {
                [self.fpsFrameTimeRow setValueText:[NSString stringWithFormat:@"%.2f ms", [fps.frameTimeMs doubleValue]] isAvailable:YES];
            } else {
                [self.fpsFrameTimeRow setValueText:nil isAvailable:NO];
            }

            [self.fpsApiRow setValueText:fps.graphicsApi ?: @"DirectX / Vulkan" isAvailable:(fps.graphicsApi != nil)];
            [self.fpsStatusRow setValueText:@"Presenting" isAvailable:YES];
            if (fps.activeProcess.length > 0) {
                [self.fpsCard setSubtitle:fps.activeProcess];
            } else {
                [self.fpsCard setSubtitle:@"Real-Time PresentMon"];
            }
        } else {
            if (![self.fpsHeroLabel.text isEqualToString:@"--"]) {
                self.fpsHeroLabel.text = @"--";
            }
            if (![self.fpsHeroSubtext.text isEqualToString:@"DESKTOP IDLE"]) {
                self.fpsHeroSubtext.text = @"DESKTOP IDLE";
                self.fpsHeroSubtext.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
            }
            [self.fpsCard setBadge:@"STANDBY"];
            [self.fpsCard setSubtitle:@"Desktop / Idle"];
            [self.fpsProgressBar setProgress:0.0 animated:NO];

            [self.fpsProcessRow setValueText:@"Idle / Desktop" isAvailable:YES];
            [self.fpsFrameTimeRow setValueText:nil isAvailable:NO];
            [self.fpsApiRow setValueText:nil isAvailable:NO];
            [self.fpsStatusRow setValueText:@"Waiting for 3D App" isAvailable:YES];
        }
    } else {
        if (![self.fpsHeroLabel.text isEqualToString:@"--"]) {
            self.fpsHeroLabel.text = @"--";
        }
        if (![self.fpsHeroSubtext.text isEqualToString:@"STANDBY"]) {
            self.fpsHeroSubtext.text = @"STANDBY";
            self.fpsHeroSubtext.textColor = [UIColor colorWithRed:122.0/255.0 green:139.0/255.0 blue:169.0/255.0 alpha:1.0];
        }
        [self.fpsCard setBadge:@"ETW"];
        [self.fpsCard setSubtitle:@"PresentMon Engine"];
        [self.fpsProgressBar setProgress:0.0 animated:NO];

        [self.fpsProcessRow setValueText:nil isAvailable:NO];
        [self.fpsFrameTimeRow setValueText:nil isAvailable:NO];
        [self.fpsApiRow setValueText:nil isAvailable:NO];
        [self.fpsStatusRow setValueText:@"Inactive" isAvailable:NO];
    }
}

- (void)updateMemoryWithSnapshot:(nullable PRMMemorySnapshot *)mem {
    if (mem && [mem.status isEqualToString:@"ok"]) {
        if (mem.usagePercent) {
            double pct = [mem.usagePercent doubleValue];
            NSString *targetStr = [NSString stringWithFormat:@"%.0f", pct];
            if (![self.ramPercentLabel.text isEqualToString:targetStr]) {
                self.ramPercentLabel.text = targetStr;
            }
            [self.ramProgressBar setProgress:(pct / 100.0) animated:YES];
        } else {
            if (![self.ramPercentLabel.text isEqualToString:@"--"]) {
                self.ramPercentLabel.text = @"--";
            }
            [self.ramProgressBar setProgress:0.0 animated:NO];
        }

        NSString *usedFmt = FormatBytes(mem.usedBytes);
        NSString *availFmt = FormatBytes(mem.availableBytes);
        NSString *totFmt = FormatBytes(mem.totalBytes);

        [self.ramUsedRow setValueText:usedFmt isAvailable:YES];
        [self.ramAvailRow setValueText:availFmt isAvailable:YES];
        [self.ramTotalRow setValueText:totFmt isAvailable:YES];
        [self.ramAllocRow setValueText:[NSString stringWithFormat:@"%@ of %@", usedFmt, totFmt] isAvailable:YES];
        [self.memoryCard setBadge:totFmt];
    } else {
        if (![self.ramPercentLabel.text isEqualToString:@"--"]) {
            self.ramPercentLabel.text = @"--";
        }
        [self.ramProgressBar setProgress:0.0 animated:NO];
        [self.ramUsedRow setValueText:nil isAvailable:NO];
        [self.ramAvailRow setValueText:nil isAvailable:NO];
        [self.ramTotalRow setValueText:nil isAvailable:NO];
        [self.ramAllocRow setValueText:nil isAvailable:NO];
    }
}

- (void)updateStorageWithSnapshot:(nullable PRMStorageSnapshot *)storage {
    CGFloat cW = 292.0;
    CGFloat cH = self.storageCard.contentContainerView.bounds.size.height;
    if (cH <= 0) cH = 280.0;

    // Anchor fixed bottom divider and I/O rows
    CGFloat divY = cH - 84.0;
    CGRect targetDivFrame = CGRectMake(0, divY, cW, 1.0);
    if (!CGRectEqualToRect(self.storageDivider.frame, targetDivFrame)) {
        self.storageDivider.frame = targetDivFrame;
        self.ioReadRow.frame = CGRectMake(0, divY + 8.0, cW, 22.0);
        self.ioWriteRow.frame = CGRectMake(0, divY + 32.0, cW, 22.0);
        self.ioStatusRow.frame = CGRectMake(0, divY + 56.0, cW, 22.0);
    }

    // Scroll view sits above divider
    CGFloat scrollH = divY - 4.0;
    CGRect targetScrollFrame = CGRectMake(0, 0, cW, scrollH);
    if (!CGRectEqualToRect(self.volumesScrollView.frame, targetScrollFrame)) {
        self.volumesScrollView.frame = targetScrollFrame;
    }

    if (!storage || ![storage.status isEqualToString:@"ok"]) {
        if (![self.vol0HeaderLabel.text isEqualToString:@"No storage volumes detected"]) {
            self.vol0HeaderLabel.text = @"No storage volumes detected";
        }
        self.vol0HeaderLabel.hidden = NO;
        self.vol0HeaderLabel.frame = CGRectMake(0, 2.0, cW, 18.0);
        self.vol0Bar.hidden = YES;
        self.vol0SubtextLabel.hidden = YES;
        self.vol1HeaderLabel.hidden = YES;
        self.vol1Bar.hidden = YES;
        self.vol1SubtextLabel.hidden = YES;
        self.vol2HeaderLabel.hidden = YES;
        self.vol2Bar.hidden = YES;
        self.vol2SubtextLabel.hidden = YES;
        self.extraVolumesLabel.hidden = YES;
        self.volumesScrollView.contentSize = CGSizeMake(cW, 24.0);
        [self.ioReadRow setValueText:nil isAvailable:NO];
        [self.ioWriteRow setValueText:nil isAvailable:NO];
        [self.ioStatusRow setValueText:nil isAvailable:NO];
        [self.storageCard setBadge:@"0 Drives"];
        return;
    }

    NSArray<PRMVolumeSnapshot *> *vols = storage.volumes;
    CGFloat curY = 2.0;

    NSUInteger removableCount = 0;
    for (PRMVolumeSnapshot *vItem in vols) {
        if (vItem.isRemovable) {
            removableCount++;
        }
    }

    // Volume 0
    if (vols.count > 0) {
        PRMVolumeSnapshot *v0 = vols[0];
        double pct = v0.usagePercent ? [v0.usagePercent doubleValue] : 0.0;
        NSString *v0Tag = v0.isRemovable ? @"[USB] " : @"";
        NSString *h0 = [NSString stringWithFormat:@"%@Drive %@ (%@) \u2022 %.0f%%", v0Tag, v0.mount, v0.fstype, pct];
        if (![self.vol0HeaderLabel.text isEqualToString:h0]) {
            self.vol0HeaderLabel.text = h0;
        }
        [self.vol0Bar setProgress:(pct / 100.0) animated:YES];
        NSString *s0 = [NSString stringWithFormat:@"%@ free of %@", FormatBytes(v0.freeBytes), FormatBytes(v0.totalBytes)];
        if (![self.vol0SubtextLabel.text isEqualToString:s0]) {
            self.vol0SubtextLabel.text = s0;
        }

        CGRect h0F = CGRectMake(0, curY, cW, 18.0);
        if (!CGRectEqualToRect(self.vol0HeaderLabel.frame, h0F)) self.vol0HeaderLabel.frame = h0F;
        CGRect b0F = CGRectMake(0, curY + 20.0, cW, 6.0);
        if (!CGRectEqualToRect(self.vol0Bar.frame, b0F)) self.vol0Bar.frame = b0F;
        CGRect sub0F = CGRectMake(0, curY + 28.0, cW, 16.0);
        if (!CGRectEqualToRect(self.vol0SubtextLabel.frame, sub0F)) self.vol0SubtextLabel.frame = sub0F;

        if (self.vol0HeaderLabel.hidden) self.vol0HeaderLabel.hidden = NO;
        if (self.vol0Bar.hidden) self.vol0Bar.hidden = NO;
        if (self.vol0SubtextLabel.hidden) self.vol0SubtextLabel.hidden = NO;
        curY += 48.0;
    } else {
        if (!self.vol0HeaderLabel.hidden) self.vol0HeaderLabel.hidden = YES;
        if (!self.vol0Bar.hidden) self.vol0Bar.hidden = YES;
        if (!self.vol0SubtextLabel.hidden) self.vol0SubtextLabel.hidden = YES;
    }

    // Volume 1
    if (vols.count > 1) {
        PRMVolumeSnapshot *v1 = vols[1];
        double pct = v1.usagePercent ? [v1.usagePercent doubleValue] : 0.0;
        NSString *v1Tag = v1.isRemovable ? @"[USB] " : @"";
        NSString *h1 = [NSString stringWithFormat:@"%@Drive %@ (%@) \u2022 %.0f%%", v1Tag, v1.mount, v1.fstype, pct];
        if (![self.vol1HeaderLabel.text isEqualToString:h1]) {
            self.vol1HeaderLabel.text = h1;
        }
        [self.vol1Bar setProgress:(pct / 100.0) animated:YES];
        NSString *s1 = [NSString stringWithFormat:@"%@ free of %@", FormatBytes(v1.freeBytes), FormatBytes(v1.totalBytes)];
        if (![self.vol1SubtextLabel.text isEqualToString:s1]) {
            self.vol1SubtextLabel.text = s1;
        }

        CGRect h1F = CGRectMake(0, curY, cW, 18.0);
        if (!CGRectEqualToRect(self.vol1HeaderLabel.frame, h1F)) self.vol1HeaderLabel.frame = h1F;
        CGRect b1F = CGRectMake(0, curY + 20.0, cW, 6.0);
        if (!CGRectEqualToRect(self.vol1Bar.frame, b1F)) self.vol1Bar.frame = b1F;
        CGRect sub1F = CGRectMake(0, curY + 28.0, cW, 16.0);
        if (!CGRectEqualToRect(self.vol1SubtextLabel.frame, sub1F)) self.vol1SubtextLabel.frame = sub1F;

        if (self.vol1HeaderLabel.hidden) self.vol1HeaderLabel.hidden = NO;
        if (self.vol1Bar.hidden) self.vol1Bar.hidden = NO;
        if (self.vol1SubtextLabel.hidden) self.vol1SubtextLabel.hidden = NO;
        curY += 48.0;
    } else {
        if (!self.vol1HeaderLabel.hidden) self.vol1HeaderLabel.hidden = YES;
        if (!self.vol1Bar.hidden) self.vol1Bar.hidden = YES;
        if (!self.vol1SubtextLabel.hidden) self.vol1SubtextLabel.hidden = YES;
    }

    // Volume 2 (Dynamic Drive)
    if (vols.count > 2) {
        PRMVolumeSnapshot *v2 = vols[2];
        double pct = v2.usagePercent ? [v2.usagePercent doubleValue] : 0.0;
        NSString *v2Tag = v2.isRemovable ? @"[USB] " : @"";
        NSString *h2 = [NSString stringWithFormat:@"%@Drive %@ (%@) \u2022 %.0f%%", v2Tag, v2.mount, v2.fstype, pct];
        if (![self.vol2HeaderLabel.text isEqualToString:h2]) {
            self.vol2HeaderLabel.text = h2;
        }
        [self.vol2Bar setProgress:(pct / 100.0) animated:YES];
        NSString *s2 = [NSString stringWithFormat:@"%@ free of %@", FormatBytes(v2.freeBytes), FormatBytes(v2.totalBytes)];
        if (![self.vol2SubtextLabel.text isEqualToString:s2]) {
            self.vol2SubtextLabel.text = s2;
        }

        CGRect h2F = CGRectMake(0, curY, cW, 18.0);
        if (!CGRectEqualToRect(self.vol2HeaderLabel.frame, h2F)) self.vol2HeaderLabel.frame = h2F;
        CGRect b2F = CGRectMake(0, curY + 20.0, cW, 6.0);
        if (!CGRectEqualToRect(self.vol2Bar.frame, b2F)) self.vol2Bar.frame = b2F;
        CGRect sub2F = CGRectMake(0, curY + 28.0, cW, 16.0);
        if (!CGRectEqualToRect(self.vol2SubtextLabel.frame, sub2F)) self.vol2SubtextLabel.frame = sub2F;

        if (self.vol2HeaderLabel.hidden) self.vol2HeaderLabel.hidden = NO;
        if (self.vol2Bar.hidden) self.vol2Bar.hidden = NO;
        if (self.vol2SubtextLabel.hidden) self.vol2SubtextLabel.hidden = NO;
        curY += 48.0;
    } else {
        if (!self.vol2HeaderLabel.hidden) self.vol2HeaderLabel.hidden = YES;
        if (!self.vol2Bar.hidden) self.vol2Bar.hidden = YES;
        if (!self.vol2SubtextLabel.hidden) self.vol2SubtextLabel.hidden = YES;
    }

    // Extra volumes indicator if vols.count > 3
    if (vols.count > 3) {
        NSUInteger extraCount = vols.count - 3;
        NSMutableArray *extraNames = [NSMutableArray arrayWithCapacity:extraCount];
        for (NSUInteger i = 3; i < vols.count; i++) {
            PRMVolumeSnapshot *vx = vols[i];
            NSString *vxTag = vx.isRemovable ? @"[USB] " : @"";
            [extraNames addObject:[NSString stringWithFormat:@"%@%@ (%@ free)", vxTag, vx.mount, FormatBytes(vx.freeBytes)]];
        }
        NSString *extraSummary = [extraNames componentsJoinedByString:@" \u2022 "];
        NSString *extraText = [NSString stringWithFormat:@"+%lu more: %@", (unsigned long)extraCount, extraSummary];
        if (![self.extraVolumesLabel.text isEqualToString:extraText]) {
            self.extraVolumesLabel.text = extraText;
        }
        CGRect extraF = CGRectMake(0, curY, cW, 18.0);
        if (!CGRectEqualToRect(self.extraVolumesLabel.frame, extraF)) self.extraVolumesLabel.frame = extraF;
        if (self.extraVolumesLabel.hidden) self.extraVolumesLabel.hidden = NO;
        curY += 22.0;
    } else {
        if (!self.extraVolumesLabel.hidden) self.extraVolumesLabel.hidden = YES;
    }

    // Update dynamic contentSize for the scroll view
    CGSize targetContentSize = CGSizeMake(cW, curY + 4.0);
    if (!CGSizeEqualToSize(self.volumesScrollView.contentSize, targetContentSize)) {
        self.volumesScrollView.contentSize = targetContentSize;
    }

    // Dynamic Card Badge & Subtitle
    NSString *badgeText = (vols.count == 1) ? @"1 Drive" : [NSString stringWithFormat:@"%lu Drives", (unsigned long)vols.count];
    if (removableCount > 0) {
        badgeText = [NSString stringWithFormat:@"%@ (%lu USB)", badgeText, (unsigned long)removableCount];
    }
    [self.storageCard setBadge:badgeText];
    [self.storageCard setSubtitle:[NSString stringWithFormat:@"%lu Mounted %@", (unsigned long)vols.count, (vols.count == 1 ? @"Volume" : @"Volumes")]];
    // Disk I/O Rates (honest unavailable handling)
    if (storage.ioAvailable) {
        [self.ioReadRow setValueText:FormatRate(storage.readBytesPerSecond) isAvailable:YES];
        [self.ioWriteRow setValueText:FormatRate(storage.writeBytesPerSecond) isAvailable:YES];
        double r = [storage.readBytesPerSecond doubleValue];
        double w = [storage.writeBytesPerSecond doubleValue];
        NSString *statusStr = (r == 0 && w == 0) ? @"IDLE" : @"ACTIVE";
        [self.ioStatusRow setValueText:statusStr isAvailable:YES];
    } else {
        [self.ioReadRow setValueText:nil isAvailable:NO];
        [self.ioWriteRow setValueText:nil isAvailable:NO];
        [self.ioStatusRow setValueText:nil isAvailable:NO];
    }
}

- (void)updateNetworkWithSnapshot:(nullable PRMNetworkSnapshot *)net system:(nullable PRMSystemSnapshot *)sys {
    if (net && [net.status isEqualToString:@"ok"]) {
        [self.netDownRow setValueText:FormatRate(net.downloadBytesPerSecond) isAvailable:YES];
        [self.netUpRow setValueText:FormatRate(net.uploadBytesPerSecond) isAvailable:YES];
        [self.netAdapterRow setValueText:net.primaryInterface ?: @"Ethernet" isAvailable:YES];
        [self.networkCard setBadge:net.primaryInterface ?: @"Tethered"];
    } else {
        [self.netDownRow setValueText:nil isAvailable:NO];
        [self.netUpRow setValueText:nil isAvailable:NO];
        [self.netAdapterRow setValueText:nil isAvailable:NO];
    }

    if (sys) {
        [self.sysHostRow setValueText:sys.hostname ?: @"PC" isAvailable:YES];
        [self.sysOsRow setValueText:sys.os ?: @"Windows" isAvailable:YES];
        [self.sysUptimeRow setValueText:FormatUptime(sys.uptimeSeconds) isAvailable:YES];
    }
}

#pragma mark - Orientation & Status Bar

- (BOOL)shouldAutorotate {
    return YES;
}

- (UIInterfaceOrientationMask)supportedInterfaceOrientations {
    return UIInterfaceOrientationMaskLandscape;
}

- (UIInterfaceOrientation)preferredInterfaceOrientationForPresentation {
    return UIInterfaceOrientationLandscapeLeft;
}

- (BOOL)prefersStatusBarHidden {
    return YES;
}

@end
