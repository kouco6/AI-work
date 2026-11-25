/**
 * 修复 Windows 上解压 harness-engine 后的「pnpm 符号链接缺失」问题（免管理员）。
 *
 * 背景：官方 `harness-engine.tar.gz` 是 pnpm workspace 的产物，靠 node_modules 符号链接
 * 解析依赖；Windows 的 `tar` 解压**不会还原符号链接**（且 `mklink`/`ln -s` 需管理员权限），
 * 引擎启动即报 `Cannot find package ...`。
 *
 * 做法：pnpm 的 hoisted 层 `node_modules/.pnpm/node_modules/` 里是**真实目录**，
 * 用 **junction**（NTFS 目录联接，`fs.symlinkSync(target, link, 'junction')`，**不需管理员**）
 * 把它链到各 workspace 的 `node_modules` 下。
 *
 * 用法::
 *
 *     node itc-tools/relink-engine.mjs <harness-engine-dist>
 *
 * 之后 `node <dist>/apps/cli/lib/bin.js --version` 应输出引擎版本。
 */
import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve(process.argv[2] || 'harness-engine-dist');
const hoistedRoot = path.join(dist, 'node_modules', '.pnpm', 'node_modules');
if (!fs.existsSync(hoistedRoot)) {
  console.error(`找不到 hoisted 层：${hoistedRoot}\n（请确认已解压 harness-engine.tar.gz）`);
  process.exit(1);
}

// 收集所有含 node_modules 的 workspace 目录
const roots = new Set([path.join(dist, 'node_modules')]);
const walk = (dir) => {
  if (!fs.existsSync(dir)) return;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!e.isDirectory()) continue;
    const p = path.join(dir, e.name);
    const nm = path.join(p, 'node_modules');
    if (fs.existsSync(nm)) roots.add(nm);
    walk(p);
  }
};
for (const g of ['apps', 'packages', 'python', 'native', 'vendor']) walk(path.join(dist, g));

const entries = fs.readdirSync(hoistedRoot);
let made = 0;
let skipped = 0;
let failed = 0;

for (const nm of roots) {
  for (const name of entries) {
    if (name.startsWith('@')) {
      const sc = path.join(hoistedRoot, name);
      if (!fs.existsSync(sc)) continue;
      const scDest = path.join(nm, name);
      fs.mkdirSync(scDest, { recursive: true });
      for (const pkg of fs.readdirSync(sc)) {
        const link = path.join(scDest, pkg);
        if (fs.existsSync(link)) { skipped++; continue; }
        try { fs.symlinkSync(path.join(sc, pkg), link, 'junction'); made++; } catch { failed++; }
      }
    } else {
      const link = path.join(nm, name);
      if (fs.existsSync(link)) { skipped++; continue; }
      try { fs.symlinkSync(path.join(hoistedRoot, name), link, 'junction'); made++; } catch { failed++; }
    }
  }
}

console.log(`junction 补建完成：新建 ${made}，已存在 ${skipped}，失败 ${failed}，覆盖 ${roots.size} 个 node_modules`);
console.log(`自检：node ${path.join(dist, 'apps', 'cli', 'lib', 'bin.js')} --version`);
