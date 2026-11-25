"""itc 平台服务层模块：挂载到 StaffDeck ModuleRegistry。

每个模块暴露一个 ``register(registry: ModuleRegistry, ctx: Mapping[str, Any]) -> None``，
供 ``harness_modules`` 配置以 ``pkg.mod:register`` 形式加载（见
``staffdeck_harness/modules/registry.py:507-516``）。

模块骨架（与 StaffDeck 自带 observer 对齐，见 ``modules/builtin.py:131-137,270``）：:

    class XxxObserver:
        name = "observer.xxx"
        def on_event(self, tenant_id, session_id, event_type, payload): ...

    def register(registry, ctx):
        registry.install(
            manifest("xxx", "名称", kind=ModuleKind.TRUSTED,
                     slots=[SlotName.EVENT_OBSERVER], provides=["event.observe/v1"]),
            XxxObserver(), slot=SlotName.EVENT_OBSERVER)
"""

__all__: list[str] = []
