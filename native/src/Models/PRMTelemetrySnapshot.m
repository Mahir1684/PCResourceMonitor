#import "PRMTelemetrySnapshot.h"

#pragma mark - Helper Functions

static NSString * _Nullable SafeString(NSDictionary * _Nullable dict, NSString *key) {
    if (![dict isKindOfClass:[NSDictionary class]]) return nil;
    id val = dict[key];
    if ([val isKindOfClass:[NSString class]]) return val;
    if ([val isKindOfClass:[NSNumber class]]) return [val stringValue];
    return nil;
}

static NSNumber * _Nullable SafeNumber(NSDictionary * _Nullable dict, NSString *key) {
    if (![dict isKindOfClass:[NSDictionary class]]) return nil;
    id val = dict[key];
    if ([val isKindOfClass:[NSNumber class]]) return val;
    if ([val isKindOfClass:[NSString class]]) {
        NSScanner *scanner = [NSScanner scannerWithString:val];
        double d;
        if ([scanner scanDouble:&d]) {
            return @(d);
        }
    }
    return nil;
}

static NSDictionary * _Nullable SafeDict(NSDictionary * _Nullable dict, NSString *key) {
    if (![dict isKindOfClass:[NSDictionary class]]) return nil;
    id val = dict[key];
    if ([val isKindOfClass:[NSDictionary class]]) return val;
    return nil;
}

static NSArray * _Nullable SafeArray(NSDictionary * _Nullable dict, NSString *key) {
    if (![dict isKindOfClass:[NSDictionary class]]) return nil;
    id val = dict[key];
    if ([val isKindOfClass:[NSArray class]]) return val;
    return nil;
}

static uint64_t SafeUInt64(NSDictionary * _Nullable dict, NSString *key) {
    NSNumber *num = SafeNumber(dict, key);
    return num ? [num unsignedLongLongValue] : 0ULL;
}

#pragma mark - PRMCpuSnapshot

@implementation PRMCpuSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        _usagePercent = SafeNumber(dict, @"usage_percent");
        _frequencyMhz = SafeNumber(dict, @"frequency_mhz");
        _coresPhysical = SafeNumber(dict, @"cores_physical");
        _coresLogical = SafeNumber(dict, @"cores_logical");

        NSDictionary *tempDict = SafeDict(dict, @"temperature_c");
        if (tempDict && [SafeString(tempDict, @"status") isEqualToString:@"ok"]) {
            _temperatureC = SafeNumber(tempDict, @"value");
            _temperatureAvailable = (_temperatureC != nil);
        } else {
            _temperatureC = nil;
            _temperatureAvailable = NO;
        }

        NSArray *rawCores = SafeArray(dict, @"per_core_percent");
        if (rawCores) {
            NSMutableArray<NSNumber *> *cores = [NSMutableArray arrayWithCapacity:rawCores.count];
            for (id item in rawCores) {
                if ([item isKindOfClass:[NSNumber class]]) {
                    [cores addObject:item];
                }
            }
            _perCorePercent = [cores copy];
        } else {
            _perCorePercent = @[];
        }
    }
    return self;
}

@end

#pragma mark - PRMGpuDeviceSnapshot

@implementation PRMGpuDeviceSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _name = SafeString(dict, @"name") ?: @"Unknown GPU";
        _vendorId = SafeString(dict, @"vendor_id") ?: @"";

        NSString *lowerName = [_name lowercaseString];
        NSString *lowerVid = [_vendorId lowercaseString];

        _isNvidia = [lowerVid isEqualToString:@"0x10de"] ||
                    ([lowerName rangeOfString:@"nvidia"].location != NSNotFound) ||
                    ([lowerName rangeOfString:@"geforce"].location != NSNotFound);

        _isAmd = [lowerVid isEqualToString:@"0x1002"] ||
                 ([lowerName rangeOfString:@"amd"].location != NSNotFound) ||
                 ([lowerName rangeOfString:@"radeon"].location != NSNotFound);

        NSDictionary *utilDict = SafeDict(dict, @"utilization_percent");
        if (utilDict && [SafeString(utilDict, @"status") isEqualToString:@"ok"]) {
            _utilizationPercent = SafeNumber(utilDict, @"value");
            _utilizationAvailable = (_utilizationPercent != nil);
        } else {
            _utilizationPercent = nil;
            _utilizationAvailable = NO;
        }

        NSDictionary *tempDict = SafeDict(dict, @"temperature_c");
        if (tempDict && [SafeString(tempDict, @"status") isEqualToString:@"ok"]) {
            _temperatureC = SafeNumber(tempDict, @"value");
            _temperatureAvailable = (_temperatureC != nil);
        } else {
            _temperatureC = nil;
            _temperatureAvailable = NO;
        }

        _powerWatts = SafeNumber(dict, @"power_watts");
        _powerAvailable = (_powerWatts != nil);

        NSDictionary *clocksDict = SafeDict(dict, @"clocks_mhz");
        if (clocksDict) {
            _graphicsClockMhz = SafeNumber(clocksDict, @"graphics");
            _graphicsClockAvailable = (_graphicsClockMhz != nil);
        } else {
            _graphicsClockMhz = nil;
            _graphicsClockAvailable = NO;
        }

        NSDictionary *memDict = SafeDict(dict, @"memory");
        NSDictionary *dedDict = memDict ? SafeDict(memDict, @"dedicated") : nil;
        if (dedDict && [SafeString(dedDict, @"status") isEqualToString:@"ok"]) {
            _vramUsedBytes = SafeUInt64(dedDict, @"used_bytes");
            _vramTotalBytes = SafeUInt64(dedDict, @"total_bytes");
            _vramAvailable = (_vramTotalBytes > 0);
        } else {
            _vramUsedBytes = 0;
            _vramTotalBytes = 0;
            _vramAvailable = NO;
        }
    }
    return self;
}

@end

#pragma mark - PRMGpusSnapshot

@implementation PRMGpusSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        NSArray *rawDevices = SafeArray(dict, @"devices");
        NSMutableArray<PRMGpuDeviceSnapshot *> *devs = [NSMutableArray array];

        PRMGpuDeviceSnapshot *foundNvidia = nil;
        PRMGpuDeviceSnapshot *foundAmd = nil;

        if (rawDevices) {
            for (id dItem in rawDevices) {
                if ([dItem isKindOfClass:[NSDictionary class]]) {
                    PRMGpuDeviceSnapshot *device = [[PRMGpuDeviceSnapshot alloc] initWithDictionary:dItem];
                    if (device) {
                        [devs addObject:device];
                        if (device.isNvidia && !foundNvidia) {
                            foundNvidia = device;
                        } else if (device.isAmd && !foundAmd) {
                            foundAmd = device;
                        }
                    }
                }
            }
        }

        _devices = [devs copy];
        _nvidiaDevice = foundNvidia;
        _amdDevice = foundAmd;
    }
    return self;
}

@end

#pragma mark - PRMMemorySnapshot

@implementation PRMMemorySnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        _totalBytes = SafeUInt64(dict, @"total_bytes");
        _usedBytes = SafeUInt64(dict, @"used_bytes");
        _availableBytes = SafeUInt64(dict, @"available_bytes");
        _usagePercent = SafeNumber(dict, @"usage_percent");
    }
    return self;
}

@end

#pragma mark - PRMVolumeSnapshot

@implementation PRMVolumeSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _device = SafeString(dict, @"device") ?: @"";
        _mount = SafeString(dict, @"mount") ?: _device;
        _fstype = SafeString(dict, @"fstype") ?: @"NTFS";
        _totalBytes = SafeUInt64(dict, @"total_bytes");
        _usedBytes = SafeUInt64(dict, @"used_bytes");
        _freeBytes = SafeUInt64(dict, @"free_bytes");
        _usagePercent = SafeNumber(dict, @"usage_percent");
        NSNumber *remNum = SafeNumber(dict, @"is_removable");
        _isRemovable = remNum ? [remNum boolValue] : NO;
        NSString *dtype = SafeString(dict, @"drive_type");
        if (!dtype || dtype.length == 0) {
            dtype = _isRemovable ? @"removable" : @"fixed";
        }
        _driveType = dtype;
    }
    return self;
}

@end

#pragma mark - PRMStorageSnapshot

@implementation PRMStorageSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";

        NSArray *rawVolumes = SafeArray(dict, @"volumes");
        NSMutableArray<PRMVolumeSnapshot *> *vols = [NSMutableArray array];
        if (rawVolumes) {
            for (id vItem in rawVolumes) {
                if ([vItem isKindOfClass:[NSDictionary class]]) {
                    PRMVolumeSnapshot *vol = [[PRMVolumeSnapshot alloc] initWithDictionary:vItem];
                    if (vol) [vols addObject:vol];
                }
            }
        }
        _volumes = [vols copy];

        NSDictionary *ioDict = SafeDict(dict, @"io_throughput");
        if (ioDict && [SafeString(ioDict, @"status") isEqualToString:@"ok"]) {
            _readBytesPerSecond = SafeNumber(ioDict, @"read_bytes_per_second");
            _writeBytesPerSecond = SafeNumber(ioDict, @"write_bytes_per_second");
            _ioAvailable = YES;
        } else {
            _readBytesPerSecond = nil;
            _writeBytesPerSecond = nil;
            _ioAvailable = NO;
        }
    }
    return self;
}

@end

#pragma mark - PRMNetworkSnapshot

@implementation PRMNetworkSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        NSDictionary *summary = SafeDict(dict, @"summary") ?: @{};

        _primaryInterface = SafeString(summary, @"primary_interface") ?: @"Ethernet";
        _downloadBytesPerSecond = SafeNumber(summary, @"download_bytes_per_second");
        _uploadBytesPerSecond = SafeNumber(summary, @"upload_bytes_per_second");
        _summaryStatus = SafeString(summary, @"status") ?: @"unknown";
    }
    return self;
}

@end

#pragma mark - PRMSystemSnapshot

@implementation PRMSystemSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        _hostname = SafeString(dict, @"hostname") ?: @"PC-HOST";
        _os = SafeString(dict, @"os") ?: @"Windows";
        _cpuName = SafeString(dict, @"cpu_name") ?: @"CPU";
        _uptimeSeconds = SafeNumber(dict, @"uptime_seconds");
        _bootTimeTimestamp = SafeNumber(dict, @"boot_time_timestamp");
    }
    return self;
}

@end

#pragma mark - PRMFpsSnapshot

@implementation PRMFpsSnapshot

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        if (![dict isKindOfClass:[NSDictionary class]]) return nil;

        _status = SafeString(dict, @"status") ?: @"unknown";
        _fps = SafeNumber(dict, @"fps");
        _frameTimeMs = SafeNumber(dict, @"frame_time_ms");
        _activeProcess = SafeString(dict, @"active_process");
        _graphicsApi = SafeString(dict, @"graphics_api");
        NSNumber *presentingNum = SafeNumber(dict, @"is_presenting");
        _isPresenting = presentingNum ? [presentingNum boolValue] : NO;
    }
    return self;
}

@end

#pragma mark - PRMTelemetrySnapshot

@implementation PRMTelemetrySnapshot

+ (instancetype)snapshotFromJSONData:(NSData *)data error:(NSError * _Nullable * _Nullable)error {
    if (!data || data.length == 0) {
        if (error) {
            *error = [NSError errorWithDomain:@"PRMTelemetryErrorDomain"
                                         code:1001
                                     userInfo:@{NSLocalizedDescriptionKey: @"Empty or nil JSON payload"}];
        }
        return nil;
    }

    id json = [NSJSONSerialization JSONObjectWithData:data options:0 error:error];
    if (![json isKindOfClass:[NSDictionary class]]) {
        if (error && !*error) {
            *error = [NSError errorWithDomain:@"PRMTelemetryErrorDomain"
                                         code:1002
                                     userInfo:@{NSLocalizedDescriptionKey: @"Root JSON is not a dictionary"}];
        }
        return nil;
    }

    return [self snapshotFromDictionary:(NSDictionary *)json];
}

+ (instancetype)snapshotFromDictionary:(NSDictionary *)dict {
    if (![dict isKindOfClass:[NSDictionary class]]) return nil;

    PRMTelemetrySnapshot *snapshot = [[PRMTelemetrySnapshot alloc] init];
    if (snapshot) {
        snapshot->_schemaVersion = [SafeNumber(dict, @"schema_version") integerValue];
        snapshot->_sequence = SafeUInt64(dict, @"sequence");
        snapshot->_generatedAt = SafeString(dict, @"generated_at") ?: @"";
        snapshot->_overallStatus = SafeString(dict, @"overall_status") ?: @"unknown";

        NSDictionary *sections = SafeDict(dict, @"sections") ?: @{};

        NSDictionary *cpuDict = SafeDict(sections, @"cpu");
        if (cpuDict) snapshot->_cpu = [[PRMCpuSnapshot alloc] initWithDictionary:cpuDict];

        NSDictionary *gpusDict = SafeDict(sections, @"gpus");
        if (gpusDict) snapshot->_gpus = [[PRMGpusSnapshot alloc] initWithDictionary:gpusDict];

        NSDictionary *memDict = SafeDict(sections, @"memory");
        if (memDict) snapshot->_memory = [[PRMMemorySnapshot alloc] initWithDictionary:memDict];

        NSDictionary *storageDict = SafeDict(sections, @"storage");
        if (storageDict) snapshot->_storage = [[PRMStorageSnapshot alloc] initWithDictionary:storageDict];

        NSDictionary *netDict = SafeDict(sections, @"network");
        if (netDict) snapshot->_network = [[PRMNetworkSnapshot alloc] initWithDictionary:netDict];

        NSDictionary *sysDict = SafeDict(sections, @"system");
        if (sysDict) snapshot->_system = [[PRMSystemSnapshot alloc] initWithDictionary:sysDict];

        NSDictionary *fpsDict = SafeDict(sections, @"fps") ?: SafeDict(sections, @"gaming");
        if (fpsDict) snapshot->_fps = [[PRMFpsSnapshot alloc] initWithDictionary:fpsDict];
    }
    return snapshot;
}

@end

