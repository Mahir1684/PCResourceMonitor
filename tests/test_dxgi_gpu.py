"""Unit tests for DxgiGpuProvider using mocked DXGI structures and COM interfaces."""

import ctypes
from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.providers.dxgi_gpu import (
    DXGI_ADAPTER_DESC1,
    DXGI_ADAPTER_FLAG_NONE,
    DXGI_ADAPTER_FLAG_SOFTWARE,
    DxgiGpuProvider,
    LUID,
)


def test_dxgi_provider_non_windows_platform() -> None:
    """Non-Windows platforms must return empty list without error."""
    with patch("sys.platform", "linux"):
        provider = DxgiGpuProvider()
        assert not provider.is_available
        assert provider.get_adapters() == []


def test_dxgi_provider_factory_creation_failure() -> None:
    """When CreateDXGIFactory1 fails, provider handles error gracefully."""
    mock_lib = MagicMock()
    mock_lib.CreateDXGIFactory1.return_value = 0x80004005  # E_FAIL

    with (
        patch("sys.platform", "win32"),
        patch("ctypes.windll.dxgi", mock_lib, create=True),
    ):
        provider = DxgiGpuProvider()
        provider._dxgi_lib = mock_lib
        adapters = provider.get_adapters()
        assert adapters == []


"""Unit tests for DxgiGpuProvider and adapter classification."""

import ctypes
from ctypes import wintypes
from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.providers.dxgi_gpu import (
    DXGI_ADAPTER_DESC1,
    DXGI_ADAPTER_FLAG_NONE,
    DXGI_ADAPTER_FLAG_SOFTWARE,
    DxgiGpuProvider,
    Release_proto,
    VENDOR_AMD,
    VENDOR_INTEL,
    VENDOR_MICROSOFT,
    VENDOR_NVIDIA,
    classify_adapter,
    safe_com_release,
)


def test_dxgi_provider_non_windows_platform() -> None:
    """Non-Windows platforms must return empty list without error."""
    with patch("sys.platform", "linux"):
        provider = DxgiGpuProvider()
        assert not provider.is_available
        assert provider.get_adapters() == []


def test_dxgi_provider_factory_creation_failure() -> None:
    """When CreateDXGIFactory1 fails, provider handles error gracefully."""
    mock_lib = MagicMock()
    mock_lib.CreateDXGIFactory1.return_value = 0x80004005  # E_FAIL

    with (
        patch("sys.platform", "win32"),
        patch("ctypes.windll.dxgi", mock_lib, create=True),
    ):
        provider = DxgiGpuProvider()
        provider._dxgi_lib = mock_lib
        adapters = provider.get_adapters()
        assert adapters == []


def test_dxgi_classification_dedicated() -> None:
    """Explicit discrete GPU markers must classify as dedicated."""
    # NVIDIA GeForce RTX
    assert classify_adapter(
        vendor_id=VENDOR_NVIDIA,
        description="NVIDIA GeForce RTX 5060 Ti",
        dedicated_video_bytes=16 * 1024**3,
        shared_system_bytes=8 * 1024**3,
    ) == "dedicated"

    # NVIDIA Workstation Quadro / RTX
    assert classify_adapter(
        vendor_id=VENDOR_NVIDIA,
        description="NVIDIA RTX A4000",
        dedicated_video_bytes=16 * 1024**3,
        shared_system_bytes=0,
    ) == "dedicated"

    # AMD Radeon RX discrete
    assert classify_adapter(
        vendor_id=VENDOR_AMD,
        description="AMD Radeon RX 7800 XT",
        dedicated_video_bytes=16 * 1024**3,
        shared_system_bytes=8 * 1024**3,
    ) == "dedicated"

    # AMD Radeon Pro discrete
    assert classify_adapter(
        vendor_id=VENDOR_AMD,
        description="Radeon Pro W6800",
        dedicated_video_bytes=32 * 1024**3,
        shared_system_bytes=16 * 1024**3,
    ) == "dedicated"

    # Intel Arc discrete
    assert classify_adapter(
        vendor_id=VENDOR_INTEL,
        description="Intel(R) Arc(TM) A770 Graphics",
        dedicated_video_bytes=16 * 1024**3,
        shared_system_bytes=8 * 1024**3,
    ) == "dedicated"


def test_dxgi_classification_integrated() -> None:
    """Explicit APU/integrated graphics markers and zero-dedicated memory must classify as integrated."""
    # AMD Ryzen integrated APU graphics (standard 512MB carveout)
    assert classify_adapter(
        vendor_id=VENDOR_AMD,
        description="AMD Radeon(TM) Graphics",
        dedicated_video_bytes=512 * 1024**2,
        shared_system_bytes=8 * 1024**3,
    ) == "integrated"

    # AMD Ryzen integrated APU graphics with 2GB carveout configured in BIOS
    # Must NOT be misclassified as dedicated despite being > 512MB
    assert classify_adapter(
        vendor_id=VENDOR_AMD,
        description="AMD Radeon(TM) Graphics",
        dedicated_video_bytes=2 * 1024**3,
        shared_system_bytes=8 * 1024**3,
    ) == "integrated"

    # Intel UHD integrated graphics
    assert classify_adapter(
        vendor_id=VENDOR_INTEL,
        description="Intel(R) UHD Graphics 770",
        dedicated_video_bytes=128 * 1024**2,
        shared_system_bytes=8 * 1024**3,
    ) == "integrated"

    # Intel Iris Xe integrated graphics
    assert classify_adapter(
        vendor_id=VENDOR_INTEL,
        description="Intel(R) Iris(R) Xe Graphics",
        dedicated_video_bytes=0,
        shared_system_bytes=8 * 1024**3,
    ) == "integrated"

    # Dynamic system memory adapter with 0 dedicated video memory
    assert classify_adapter(
        vendor_id=0x9999,
        description="Custom Dynamic Display Controller",
        dedicated_video_bytes=0,
        shared_system_bytes=4 * 1024**3,
    ) == "integrated"


def test_dxgi_classification_unknown() -> None:
    """When naming and memory evidence is inconclusive, return unknown rather than guessing."""
    # Ambiguous vendor and model
    assert classify_adapter(
        vendor_id=0x9999,
        description="Acme Video Coprocessor",
        dedicated_video_bytes=2 * 1024**3,
        shared_system_bytes=4 * 1024**3,
    ) == "unknown"

    # Known vendor but generic unbranded description
    assert classify_adapter(
        vendor_id=VENDOR_AMD,
        description="AMD Display Adapter",
        dedicated_video_bytes=1 * 1024**3,
        shared_system_bytes=4 * 1024**3,
    ) == "unknown"

    # Empty string description
    assert classify_adapter(
        vendor_id=0,
        description="",
        dedicated_video_bytes=1024,
        shared_system_bytes=1024,
    ) == "unknown"


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_dxgi_safe_com_release() -> None:
    """safe_com_release must handle null pointers, valid interfaces, and release errors safely."""
    # 1. Null / zero pointers must be safely ignored
    safe_com_release(None)
    safe_com_release(ctypes.c_void_p(0))

    # 2. Valid COM interface pointer must invoke Release exactly once
    release_calls = []

    @Release_proto
    def mock_release(this: int) -> int:
        release_calls.append(this)
        return 0

    vtbl = (ctypes.c_void_p * 3)(
        None, None,
        ctypes.cast(mock_release, ctypes.c_void_p).value,
    )
    obj = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(vtbl), ctypes.c_void_p).value)
    p_obj = ctypes.cast(ctypes.pointer(obj), ctypes.c_void_p)

    safe_com_release(p_obj)
    assert len(release_calls) == 1

    # 3. Release errors must be caught and logged without raising or crashing
    @Release_proto
    def mock_failing_release(this: int) -> int:
        raise RuntimeError("COM release simulated failure")

    vtbl_fail = (ctypes.c_void_p * 3)(
        None, None,
        ctypes.cast(mock_failing_release, ctypes.c_void_p).value,
    )
    obj_fail = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(vtbl_fail), ctypes.c_void_p).value)
    p_obj_fail = ctypes.cast(ctypes.pointer(obj_fail), ctypes.c_void_p)

    # Must not raise
    safe_com_release(p_obj_fail)


def test_dxgi_get_adapters_mocked_success_and_filtering() -> None:
    """Mocked DXGI enumeration must parse physical adapters, filter software renderers, and release COM objects."""
    factory_released = []
    adapter_released = []

    @Release_proto
    def mock_factory_release(this: int) -> int:
        factory_released.append(this)
        return 0

    @Release_proto
    def mock_adapter_release(this: int) -> int:
        adapter_released.append(this)
        return 0

    EnumAdapters1_proto = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
    )

    GetDesc1_proto = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.POINTER(DXGI_ADAPTER_DESC1),
    )

    # Adapter 0: Physical NVIDIA GPU
    @GetDesc1_proto
    def mock_get_desc_nv(this: int, p_desc: ctypes.POINTER(DXGI_ADAPTER_DESC1)) -> int:
        desc = p_desc.contents
        desc.Description = "NVIDIA GeForce RTX 5060 Ti"
        desc.VendorId = VENDOR_NVIDIA
        desc.DeviceId = 0x2800
        desc.DedicatedVideoMemory = 16 * 1024**3
        desc.SharedSystemMemory = 8 * 1024**3
        desc.Flags = DXGI_ADAPTER_FLAG_NONE
        desc.AdapterLuid.HighPart = 0
        desc.AdapterLuid.LowPart = 12345
        return 0

    vtbl_nv = (ctypes.c_void_p * 11)(
        None, None,
        ctypes.cast(mock_adapter_release, ctypes.c_void_p).value,
        None, None, None, None, None, None, None,
        ctypes.cast(mock_get_desc_nv, ctypes.c_void_p).value,
    )
    obj_nv = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(vtbl_nv), ctypes.c_void_p).value)
    p_nv = ctypes.cast(ctypes.pointer(obj_nv), ctypes.c_void_p)

    # Adapter 1: Software WARP Renderer (Must be filtered out)
    @GetDesc1_proto
    def mock_get_desc_warp(this: int, p_desc: ctypes.POINTER(DXGI_ADAPTER_DESC1)) -> int:
        desc = p_desc.contents
        desc.Description = "Microsoft Basic Render Driver"
        desc.VendorId = VENDOR_MICROSOFT
        desc.Flags = DXGI_ADAPTER_FLAG_SOFTWARE
        return 0

    vtbl_warp = (ctypes.c_void_p * 11)(
        None, None,
        ctypes.cast(mock_adapter_release, ctypes.c_void_p).value,
        None, None, None, None, None, None, None,
        ctypes.cast(mock_get_desc_warp, ctypes.c_void_p).value,
    )
    obj_warp = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(vtbl_warp), ctypes.c_void_p).value)
    p_warp = ctypes.cast(ctypes.pointer(obj_warp), ctypes.c_void_p)

    # Factory enumeration: idx 0 -> NVIDIA, idx 1 -> WARP, idx 2 -> NOT_FOUND (-2005270526)
    @EnumAdapters1_proto
    def mock_enum_adapters(this: int, idx: int, pp_adapter: ctypes.POINTER(ctypes.c_void_p)) -> int:
        if idx == 0:
            pp_adapter.contents.value = p_nv.value
            return 0
        elif idx == 1:
            pp_adapter.contents.value = p_warp.value
            return 0
        return -2005270526  # DXGI_ERROR_NOT_FOUND

    factory_vtbl = (ctypes.c_void_p * 13)(
        None, None,
        ctypes.cast(mock_factory_release, ctypes.c_void_p).value,
        None, None, None, None, None, None, None, None, None,
        ctypes.cast(mock_enum_adapters, ctypes.c_void_p).value,
    )
    factory_obj = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(factory_vtbl), ctypes.c_void_p).value)
    p_factory = ctypes.cast(ctypes.pointer(factory_obj), ctypes.c_void_p)

    class MockDxgiLib:
        def CreateDXGIFactory1(self, riid: Any, pp_factory: Any) -> int:
            pp_factory._obj.value = p_factory.value
            return 0

    provider = DxgiGpuProvider()
    provider._is_windows = True
    provider._dxgi_lib = MockDxgiLib()

    adapters = provider.get_adapters()

    # WARP renderer must be filtered out, leaving exactly 1 adapter
    assert len(adapters) == 1
    assert adapters[0]["name"] == "NVIDIA GeForce RTX 5060 Ti"
    assert adapters[0]["adapter_type"] == "dedicated"
    assert adapters[0]["provider"] == "dxgi"
    assert adapters[0]["luid"] == "0x00000000:0x00003039"

    # Both adapters (NVIDIA and WARP) and factory must have been released exactly once
    assert len(adapter_released) == 2
    assert len(factory_released) == 1


def test_dxgi_get_adapters_mocked_adapter_failure_cleanup() -> None:
    """When an adapter fails GetDesc1 query, its COM interface is still released safely."""
    factory_released = []
    adapter_released = []

    @Release_proto
    def mock_factory_release(this: int) -> int:
        factory_released.append(this)
        return 0

    @Release_proto
    def mock_adapter_release(this: int) -> int:
        adapter_released.append(this)
        return 0

    EnumAdapters1_proto = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
    )

    GetDesc1_proto = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.POINTER(DXGI_ADAPTER_DESC1),
    )

    # Failing adapter GetDesc1 returns E_FAIL (-2147467259)
    @GetDesc1_proto
    def mock_get_desc_fail(this: int, p_desc: ctypes.POINTER(DXGI_ADAPTER_DESC1)) -> int:
        return -2147467259

    vtbl_fail = (ctypes.c_void_p * 11)(
        None, None,
        ctypes.cast(mock_adapter_release, ctypes.c_void_p).value,
        None, None, None, None, None, None, None,
        ctypes.cast(mock_get_desc_fail, ctypes.c_void_p).value,
    )
    obj_fail = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(vtbl_fail), ctypes.c_void_p).value)
    p_fail = ctypes.cast(ctypes.pointer(obj_fail), ctypes.c_void_p)

    @EnumAdapters1_proto
    def mock_enum(this: int, idx: int, pp_adapter: ctypes.POINTER(ctypes.c_void_p)) -> int:
        if idx == 0:
            pp_adapter.contents.value = p_fail.value
            return 0
        return -2005270526

    factory_vtbl = (ctypes.c_void_p * 13)(
        None, None,
        ctypes.cast(mock_factory_release, ctypes.c_void_p).value,
        None, None, None, None, None, None, None, None, None,
        ctypes.cast(mock_enum, ctypes.c_void_p).value,
    )
    factory_obj = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.pointer(factory_vtbl), ctypes.c_void_p).value)
    p_factory = ctypes.cast(ctypes.pointer(factory_obj), ctypes.c_void_p)

    class MockDxgiLib:
        def CreateDXGIFactory1(self, riid: Any, pp_factory: Any) -> int:
            pp_factory._obj.value = p_factory.value
            return 0

    provider = DxgiGpuProvider()
    provider._is_windows = True
    provider._dxgi_lib = MockDxgiLib()

    adapters = provider.get_adapters()
    assert adapters == []

    # COM reference must be released despite query failure
    assert len(adapter_released) == 1
    assert len(factory_released) == 1


def test_dxgi_live_enumeration() -> None:
    """Test live enumeration on this Windows PC detects both physical GPUs if hardware present."""
    provider = DxgiGpuProvider()
    if not provider.is_available:
        pytest.skip("DXGI not available")

    adapters = provider.get_adapters()
    if not adapters:
        pytest.skip("No physical DXGI adapters found on host")

    names = [a["name"] for a in adapters]
    assert any("NVIDIA" in n for n in names)
    assert any("AMD" in n or "Radeon" in n for n in names)
