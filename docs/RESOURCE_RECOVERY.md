# 私有资源与换机恢复 / Private resource recovery

Git 仓库和 Release 都必须保持私有。本次不新增协作者。代码与资源使用相同备份版本 `backup-2026-09-10`；实际附件身份以 `docs/private-backup/asset-manifest.json` 为准。

## 资源组织

| 分组 | 恢复用途 | 本次附件 |
| --- | --- | --- |
| `runtime` | 当前有效 public 文件，包含地图、GLB、贴图、解码器、车辆和清单 | 4 个 ZIP |
| `authoring` | 当前 Blender 可编辑工程 | 1 个 ZIP |
| `source-assets` | 原始素材、模型来源、参考照片及有效派生输入 | 2 个 ZIP |
| `design-references` | 当前设计参考和生成说明 | 1 个 ZIP |

选中 2,024 个文件路径、6,967,439,836 字节；去重后 1,927 个内容对象、6,886,017,818 字节；ZIP 附件合计 3,665,902,411 字节。相同内容只上传一次，清单保留各自恢复路径。

历史备份、旧 Blend 自动备份、失败模型导出、转换中间版本、日志和缓存不重复打包。排除记录逐项列在资产清单的 `excluded` 中，本地原件未删除。源码目录中的 `release/open-source` 是此前未发布的候选草稿，不属于当前私有恢复版本；`release/sites` 是已有独立发布工作目录，其运行产物可由源资源和脚本重建，本次不改变其 Git 状态或站点。

## 下载与校验

先安装 GitHub CLI 并通过官方登录流程登录有访问权的账号，不把令牌写入脚本或仓库。下载附件：

```sh
gh release download backup-2026-09-10 --repo rttang/shanghai-commute-drive --pattern '*.zip' --dir .tooling/restore-downloads
python3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --verify-only
```

仅恢复网页运行资源：

```sh
python3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --group runtime
```

恢复全部所选工程和素材：

```sh
python3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --group all
```

恢复到另一个空目录可以指定 `--target /absolute/path/to/project`。脚本先核对 ZIP 大小和 SHA-256，再核对每个对象；拒绝不安全路径、符号链接和内容不同的已有文件。不要用覆盖开关绕过差异；先确认是否存在新电脑独有修改。

## Windows 原生运行

安装 Git、兼容版本的 Node、Python 3 和 GitHub CLI，重新登录。PowerShell 示例：

```powershell
git clone https://github.com/rttang/shanghai-commute-drive.git
cd shanghai-commute-drive
gh release download backup-2026-09-10 --repo rttang/shanghai-commute-drive --pattern '*.zip' --dir .tooling/restore-downloads
py -3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --group runtime
npm ci
npm run dev
```

现有完整构建含 Python 检查。若系统只有 `py -3` 而没有 `python3`，可顺序执行等价步骤：

```powershell
node node_modules/typescript/bin/tsc --noEmit
node --import tsx scripts/verify_photo_placement.mjs
node node_modules/vite/bin/vite.js build
py -3 scripts/verify_street_build.py
```

Windows 实机尚需在新电脑验证。不要把 macOS 的 Node 模块、Python 虚拟环境或 Blender 可执行文件复制后当作 Windows 依赖。

## WSL2 与建模

如果继续使用现有 Bash/Python 建模入口，建议在 WSL2 中安装 Linux 版本依赖，并把活跃仓库保存在 Linux 文件系统。Blender 需要单独安装；现有 `scripts/blender-local.sh` 使用 Mac 应用路径，须根据新环境适配后才能运行建模流程。该限制不影响已有 GLB 的网页播放。

完整 Blender 工程和源素材已纳入对应附件，但部分历史校验引用旧备份和 Mac 上的图像生成目录，不属于跨平台运行前提。`test:portable` 明确排除该历史冻结档案测试；不宣称原始 `npm test` 的所有历史检查在新电脑都可直接通过。

## 空间与清理

ZIP 下载目录、恢复目录和 dist 会额外占用空间；完整恢复时为源码、6.97 GB 资源、构建输出和依赖保留足够余量。优先在容量足够的 SSD 上恢复。

本次上传结束后的清理只面向本任务创建的临时分支／恢复工作树，并以远端下载校验成功为前提。保留 main、当前工作目录、原始图片、模型、工程及其他任务目录。删除分支引用通常不会释放大型资源；节省空间主要来自删除已核验的临时恢复工作树。任何额外删除应按具体路径另行确认。

## Verification boundary

This manifest is a private content backup, not a new asset license. Checksums prove file identity. Repository cloning does not migrate browser-local preferences/photos, account credentials, an installed Blender runtime, or historical external developer archives. Native Windows verification remains separate from local macOS restore/build/browser checks.
