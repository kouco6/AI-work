"""itc 业务库：数据表模型与服务存储。

包含本平台**新增**（StaffDeck 原生没有）的表与服务：
* ``usage``  —— 用量计量（FR-151/152）
* ``quota``  —— 配额与限流（FR-156）
* ``audit``  —— 审计留存（FR-224）
* ``safety`` —— 内容安全（FR-234）
* ``rbac``   —— 角色权限深化（FR-232/266）

数据表统一 ``itc_`` 前缀，**由 Alembic 管理**（不接管 StaffDeck 的
``backend/app/db/database.py`` 手写迁移；PG 下那些迁移被 sqlite 守卫自动跳过）。
"""

__all__: list[str] = []
