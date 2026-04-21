"""Tool registry.

Adding a new tool module:
    1. Create ``kestrel_mcp/tools/<name>_tool.py`` subclassing ``ToolModule``.
    2. Import it below and append an instance to :func:`load_modules`.
    3. Add a matching ``tools.<name>`` block to ``config/default.yaml``.
"""

from __future__ import annotations

from ..config import Settings
from ..security import ScopeGuard
from .base import ToolModule


def load_modules(settings: Settings, scope_guard: ScopeGuard) -> list[ToolModule]:
    """Instantiate every bundled tool module in a deterministic order.

    Only modules marked ``enabled=True`` in the effective configuration are
    returned. This makes it cheap to ship a conservative default config
    where dangerous modules are opt-in.
    """

    from .bloodhound_tool import BloodHoundModule
    from .caido_tool import CaidoModule
    from .engagement_tool import EngagementModule
    from .evilginx_tool import EvilginxModule
    from .ffuf_tool import FfufModule
    from .havoc_tool import HavocModule
    from .httpx_tool import HttpxModule
    from .impacket_tool import ImpacketModule
    from .ligolo_tool import LigoloModule
    from .nmap_tool import NmapModule
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
    from .subfinder_tool import SubfinderModule

    candidates: list[ToolModule] = [
        # Management / admin first — these don't depend on external binaries
        # and should always appear in the schema.
        EngagementModule(settings, scope_guard),
        # External-tool-backed modules follow.
        ShodanModule(settings, scope_guard),
        NucleiModule(settings, scope_guard),
        SubfinderModule(settings, scope_guard),
        HttpxModule(settings, scope_guard),
        NmapModule(settings, scope_guard),
        FfufModule(settings, scope_guard),
        ImpacketModule(settings, scope_guard),
        BloodHoundModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
        LigoloModule(settings, scope_guard),
        SliverModule(settings, scope_guard),
        HavocModule(settings, scope_guard),
        EvilginxModule(settings, scope_guard),
    ]
    return [m for m in candidates if m.enabled()]


__all__ = ["ToolModule", "load_modules"]
