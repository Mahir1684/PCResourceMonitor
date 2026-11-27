"""Windows DXGI graphics adapter discovery and memory provider.

Uses standard library ctypes to interact directly with dxgi.dll,
enumerating physical display adapters, matching hardware identities (LUID,
Vendor ID, Device ID), and separating dedicated video memory from shared
system memory. Excludes software/WARP renderers and guarantees COM interface
cleanup via try/finally blocks.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Any


logger = logging.getLogger(__name__)

# DXGI Adapter Flags
DXGI_ADAPTER_FLAG_NONE = 0
DXGI_ADAPTER_FLAG_REMOTE = 1
DXGI_ADAPTER_FLAG_SOFTWARE = 2

# Known PCI Vendor IDs
VENDOR_NVIDIA = 0x10DE
VENDOR_AMD = 0x1002
VENDOR_INTEL = 0x8086
VENDOR_MICROSOFT = 0x1414


def classify_adapter(
    vendor_id: int,
    description: str,
    dedicated_video_bytes: int,
    shared_system_bytes: int,
) -> str:
    """Classify a display adapter as 'dedicated', 'integrated', or 'unknown'.

    Evaluates vendor ID, adapter description naming patterns, and memory layout.
    Avoids rigid capacity thresholds and returns 'unknown' when evidence is
    inconclusive.
    """
    desc_clean = description.strip()
    desc_lower = desc_clean.lower()

    # 1. Explicit dedicated indicators
    # NVIDIA GeForce, RTX, GTX, Quadro, Tesla, Titan
    if (vendor_id == VENDOR_NVIDIA or "nvidia" in desc_lower) and any(
        m in desc_lower for m in ("geforce", "rtx", "gtx", "quadro", "tesla", "titan")
    ):
        return "dedicated"

    # AMD Radeon RX, Radeon Pro, Radeon VII, FirePro
    if any(m in desc_lower for m in ("radeon rx", "radeon pro", "radeon vii", "firepro")):
        return "dedicated"

    # Intel Arc discrete graphics
    if "arc" in desc_lower and (vendor_id == VENDOR_INTEL or "intel" in desc_lower):
        return "dedicated"

    # 2. Explicit integrated indicators
    # AMD Ryzen integrated Radeon APU graphics (e.g. "AMD Radeon(TM) Graphics")
    if "radeon(tm) graphics" in desc_lower or "radeon graphics" in desc_lower:
        return "integrated"

    # Intel integrated graphics
    if any(m in desc_lower for m in ("hd graphics", "uhd graphics", "iris", "extreme graphics")):
        return "integrated"

    # 3. Memory layout indicators
    # Adapters reporting 0 dedicated video memory and utilizing shared system memory
    if dedicated_video_bytes == 0 and shared_system_bytes > 0:
        return "integrated"

    # 4. Inconclusive evidence
    return "unknown"


# Ctypes COM definitions
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]


class DXGI_ADAPTER_DESC1(ctypes.Structure):
    _fields_ = [
        ("Description", wintypes.WCHAR * 128),
        ("VendorId", wintypes.UINT),
        ("DeviceId", wintypes.UINT),
        ("SubSysId", wintypes.UINT),
        ("Revision", wintypes.UINT),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", LUID),
        ("Flags", wintypes.UINT),
    ]


# IID_IDXGIFactory1: 770aae78-f26f-4dba-a829-253c83d1b387
IID_IDXGIFactory1 = GUID(
    0x770AAE78,
    0xF26F,
    0x4DBA,
    (wintypes.BYTE * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87),
)


Release_proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)


def safe_com_release(p_interface: ctypes.c_void_p) -> None:
    """Safely invoke IUnknown::Release on a COM interface pointer.

    Ensures that failures during release do not raise or mask other exceptions.
    """
    if not p_interface or not p_interface.value:
        return
    try:
        vtbl = ctypes.cast(
            p_interface,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ).contents
        release_func = Release_proto(vtbl[2])
        release_func(p_interface)
    except Exception as exc:
        logger.debug("COM interface release error: %s", exc)


class DxgiGpuProvider:
    """Provider for Windows display adapters using native DXGI."""

    def __init__(self) -> None:
        self._is_windows: bool = sys.platform == "win32"
        self._dxgi_lib: Any | None = None

        if self._is_windows:
            try:
                self._dxgi_lib = ctypes.windll.dxgi
            except (OSError, AttributeError) as exc:
                logger.debug("Failed to load dxgi.dll: %s", exc)
                self._dxgi_lib = None

    @property
    def is_available(self) -> bool:
        """True if running on Windows and dxgi.dll is available."""
        return self._is_windows and self._dxgi_lib is not None

    def get_adapters(self) -> list[dict[str, Any]]:
        """Enumerate all physical display adapters via DXGI.
        
        Excludes software renderers (DXGI_ADAPTER_FLAG_SOFTWARE).
        Releases all allocated COM interfaces safely.
        """
        if not self.is_available or self._dxgi_lib is None:
            return []

        p_factory = ctypes.c_void_p()
        try:
            hr = self._dxgi_lib.CreateDXGIFactory1(
                ctypes.byref(IID_IDXGIFactory1),
                ctypes.byref(p_factory),
            )
            if hr != 0 or not p_factory.value:
                logger.debug("CreateDXGIFactory1 failed with HRESULT: %s", hex(hr & 0xFFFFFFFF))
                return []
        except Exception as exc:
            logger.debug("Exception creating DXGI factory: %s", exc)
            return []

        adapters: list[dict[str, Any]] = []

        try:
            # IDXGIFactory1 vtable:
            # 0: QueryInterface, 1: AddRef, 2: Release
            # 12: EnumAdapters1(UINT Adapter, IDXGIAdapter1** ppAdapter)
            factory_vtbl = ctypes.cast(
                p_factory,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ).contents

            EnumAdapters1_proto = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                wintypes.UINT,
                ctypes.POINTER(ctypes.c_void_p),
            )
            EnumAdapters1 = EnumAdapters1_proto(factory_vtbl[12])

            GetDesc1_proto = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.POINTER(DXGI_ADAPTER_DESC1),
            )

            adapter_idx = 0
            while True:
                p_adapter = ctypes.c_void_p()
                hr_enum = EnumAdapters1(p_factory, adapter_idx, ctypes.byref(p_adapter))
                if hr_enum != 0 or not p_adapter.value:
                    break  # DXGI_ERROR_NOT_FOUND or finished enumeration

                try:
                    adapter_vtbl = ctypes.cast(
                        p_adapter,
                        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
                    ).contents
                    # IDXGIAdapter1 vtable:
                    # 0: QueryInterface, 1: AddRef, 2: Release
                    # 10: GetDesc1(DXGI_ADAPTER_DESC1* pDesc)
                    GetDesc1 = GetDesc1_proto(adapter_vtbl[10])

                    desc = DXGI_ADAPTER_DESC1()
                    hr_desc = GetDesc1(p_adapter, ctypes.byref(desc))
                    if hr_desc == 0:
                        # Exclude software renderers (e.g. Microsoft Basic Render Driver / WARP)
                        if not (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE):
                            dedicated_vram = int(desc.DedicatedVideoMemory)
                            shared_ram = int(desc.SharedSystemMemory)
                            dedicated_sys = int(desc.DedicatedSystemMemory)
                            name = str(desc.Description).strip()

                            adapter_type = classify_adapter(
                                vendor_id=desc.VendorId,
                                description=name,
                                dedicated_video_bytes=dedicated_vram,
                                shared_system_bytes=shared_ram,
                            )

                            adapters.append({
                                "index": adapter_idx,
                                "name": name,
                                "vendor_id": hex(desc.VendorId),
                                "device_id": hex(desc.DeviceId),
                                "subsys_id": hex(desc.SubSysId),
                                "revision": desc.Revision,
                                "luid": f"0x{desc.AdapterLuid.HighPart & 0xFFFFFFFF:08x}:0x{desc.AdapterLuid.LowPart:08x}",
                                "adapter_type": adapter_type,
                                "provider": "dxgi",
                                "memory_capacities": {
                                    "dedicated_video_bytes": dedicated_vram,
                                    "dedicated_system_bytes": dedicated_sys,
                                    "shared_system_bytes": shared_ram,
                                    "note": "Reported DXGI adapter memory capacities/budgets, not instantaneous utilization.",
                                },
                            })
                finally:
                    # Guarantee adapter interface release safely
                    safe_com_release(p_adapter)

                adapter_idx += 1

        finally:
            # Guarantee factory interface release safely
            safe_com_release(p_factory)

        return adapters
