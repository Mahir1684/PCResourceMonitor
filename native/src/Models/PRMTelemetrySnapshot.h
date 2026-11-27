#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

#pragma mark - CPU Snapshot

@interface PRMCpuSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, strong, readonly, nullable) NSNumber *usagePercent;
@property (nonatomic, strong, readonly, nullable) NSNumber *frequencyMhz;
@property (nonatomic, strong, readonly, nullable) NSNumber *temperatureC;
@property (nonatomic, assign, readonly) BOOL temperatureAvailable;
@property (nonatomic, strong, readonly, nullable) NSNumber *coresPhysical;
@property (nonatomic, strong, readonly, nullable) NSNumber *coresLogical;
@property (nonatomic, copy, readonly) NSArray<NSNumber *> *perCorePercent;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - GPU Device Snapshot

@interface PRMGpuDeviceSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *name;
@property (nonatomic, copy, readonly) NSString *vendorId;
@property (nonatomic, assign, readonly) BOOL isNvidia;
@property (nonatomic, assign, readonly) BOOL isAmd;
@property (nonatomic, strong, readonly, nullable) NSNumber *utilizationPercent;
@property (nonatomic, assign, readonly) BOOL utilizationAvailable;
@property (nonatomic, strong, readonly, nullable) NSNumber *temperatureC;
@property (nonatomic, assign, readonly) BOOL temperatureAvailable;
@property (nonatomic, strong, readonly, nullable) NSNumber *powerWatts;
@property (nonatomic, assign, readonly) BOOL powerAvailable;
@property (nonatomic, strong, readonly, nullable) NSNumber *graphicsClockMhz;
@property (nonatomic, assign, readonly) BOOL graphicsClockAvailable;
@property (nonatomic, assign, readonly) uint64_t vramUsedBytes;
@property (nonatomic, assign, readonly) uint64_t vramTotalBytes;
@property (nonatomic, assign, readonly) BOOL vramAvailable;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - GPUs Container Snapshot

@interface PRMGpusSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, copy, readonly) NSArray<PRMGpuDeviceSnapshot *> *devices;
@property (nonatomic, strong, readonly, nullable) PRMGpuDeviceSnapshot *nvidiaDevice;
@property (nonatomic, strong, readonly, nullable) PRMGpuDeviceSnapshot *amdDevice;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - Memory Snapshot

@interface PRMMemorySnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, assign, readonly) uint64_t totalBytes;
@property (nonatomic, assign, readonly) uint64_t usedBytes;
@property (nonatomic, assign, readonly) uint64_t availableBytes;
@property (nonatomic, strong, readonly, nullable) NSNumber *usagePercent;
@property (nonatomic, assign, readonly) BOOL isRemovable;
@property (nonatomic, copy, readonly) NSString *driveType;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - Storage Volume Snapshot

@interface PRMVolumeSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *device;
@property (nonatomic, copy, readonly) NSString *mount;
@property (nonatomic, copy, readonly) NSString *fstype;
@property (nonatomic, assign, readonly) uint64_t totalBytes;
@property (nonatomic, assign, readonly) uint64_t usedBytes;
@property (nonatomic, assign, readonly) uint64_t freeBytes;
@property (nonatomic, strong, readonly, nullable) NSNumber *usagePercent;
@property (nonatomic, assign, readonly) BOOL isRemovable;
@property (nonatomic, copy, readonly) NSString *driveType;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - Storage Container Snapshot

@interface PRMStorageSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, copy, readonly) NSArray<PRMVolumeSnapshot *> *volumes;
@property (nonatomic, strong, readonly, nullable) NSNumber *readBytesPerSecond;
@property (nonatomic, strong, readonly, nullable) NSNumber *writeBytesPerSecond;
@property (nonatomic, assign, readonly) BOOL ioAvailable;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - Network Snapshot

@interface PRMNetworkSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, copy, readonly) NSString *primaryInterface;
@property (nonatomic, strong, readonly, nullable) NSNumber *downloadBytesPerSecond;
@property (nonatomic, strong, readonly, nullable) NSNumber *uploadBytesPerSecond;
@property (nonatomic, copy, readonly) NSString *summaryStatus;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - System Snapshot

@interface PRMSystemSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, copy, readonly) NSString *hostname;
@property (nonatomic, copy, readonly) NSString *os;
@property (nonatomic, copy, readonly) NSString *cpuName;
@property (nonatomic, strong, readonly, nullable) NSNumber *uptimeSeconds;
@property (nonatomic, strong, readonly, nullable) NSNumber *bootTimeTimestamp;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - FPS / Gaming Snapshot

@interface PRMFpsSnapshot : NSObject

@property (nonatomic, copy, readonly) NSString *status;
@property (nonatomic, strong, readonly, nullable) NSNumber *fps;
@property (nonatomic, strong, readonly, nullable) NSNumber *frameTimeMs;
@property (nonatomic, copy, readonly, nullable) NSString *activeProcess;
@property (nonatomic, copy, readonly, nullable) NSString *graphicsApi;
@property (nonatomic, assign, readonly) BOOL isPresenting;

- (instancetype)initWithDictionary:(NSDictionary *)dict;

@end

#pragma mark - Root Telemetry Snapshot

@interface PRMTelemetrySnapshot : NSObject

@property (nonatomic, assign, readonly) NSInteger schemaVersion;
@property (nonatomic, assign, readonly) uint64_t sequence;
@property (nonatomic, copy, readonly) NSString *generatedAt;
@property (nonatomic, copy, readonly) NSString *overallStatus;

@property (nonatomic, strong, readonly, nullable) PRMCpuSnapshot *cpu;
@property (nonatomic, strong, readonly, nullable) PRMGpusSnapshot *gpus;
@property (nonatomic, strong, readonly, nullable) PRMMemorySnapshot *memory;
@property (nonatomic, strong, readonly, nullable) PRMStorageSnapshot *storage;
@property (nonatomic, strong, readonly, nullable) PRMNetworkSnapshot *network;
@property (nonatomic, strong, readonly, nullable) PRMSystemSnapshot *system;
@property (nonatomic, strong, readonly, nullable) PRMFpsSnapshot *fps;

+ (nullable instancetype)snapshotFromJSONData:(NSData *)data error:(NSError * _Nullable * _Nullable)error;
+ (nullable instancetype)snapshotFromDictionary:(NSDictionary *)dict;

@end

NS_ASSUME_NONNULL_END

