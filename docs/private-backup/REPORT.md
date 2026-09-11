# 私有 GitHub 上传、恢复与清理报告

## 目标和当前状态

目标仓库：`rttang/shanghai-commute-drive`；要求为 Private。保留当前完整游戏与素材，不执行公开发行、MIT 重授权或程序化替换。

当前状态（2026-09-11）：[GitHub 仓库](https://github.com/rttang/shanghai-commute-drive)及其[备份版本 backup-2026-09-10](https://github.com/rttang/shanghai-commute-drive/releases/tag/backup-2026-09-10)保持私有，8 个资源包和 2 份清单／校验附件仍在远端。第一轮完成独立恢复验证并清理临时 Git 目录；第二轮经确认删除 20 个重复备份、构建产物和下载缓存目标，约回收 9.27 GiB。当前项目约 22.69 GiB，原始开发资源保留。

## 2026-09-11 第二轮空间清理

本轮仅处理用户确认的 20 个路径，全部完成，跳过 0 项。按批准时逐目标测得的分配空间合计为 **9,952,821,248 字节，约 9.27 GiB**。项目从批准前盘点约 **31.96 GiB** 降至清理后约 **22.69 GiB**；报告与审计文件会占用少量空间，因此项目净变化与删除目标合计存在小幅差异。

| 类别 | 删除内容 | 释放分配空间 |
| --- | --- | --- |
| 本地备份副本 | 9 个 ZIP（含已替换的失败包）和旧下载目录 | 4.315 GiB |
| 构建产物 | dist 与 dist-release | 2.623 GiB |
| 发布派生资源 | deployment-optimization/runtime-assets | 0.633 GiB |
| 发布压缩包 | 4 个 tar.gz 及 1 份对应校验文件 | 1.454 GiB |
| 依赖下载缓存 | npm-cache 与 private-npm-cache | 0.245 GiB |

### 已删除的完整路径清单

- `.tooling/private-backup/backup-2026-09-10-runtime-01.zip`
- `.tooling/private-backup/backup-2026-09-10-runtime-02.zip`
- `.tooling/private-backup/backup-2026-09-10-runtime-03.zip`
- `.tooling/private-backup/backup-2026-09-10-runtime-03-r2.zip`
- `.tooling/private-backup/backup-2026-09-10-runtime-04.zip`
- `.tooling/private-backup/backup-2026-09-10-authoring-01.zip`
- `.tooling/private-backup/backup-2026-09-10-source-assets-01.zip`
- `.tooling/private-backup/backup-2026-09-10-source-assets-02.zip`
- `.tooling/private-backup/backup-2026-09-10-design-references-01.zip`
- `.tooling/private-backup/retained-disk-download`
- `dist`
- `dist-release`
- `.tooling/deployment-optimization/runtime-assets`
- `release/shanghai-commute-drive-9af5f476033e17dc.tar.gz`
- `release/shanghai-commute-drive-9af5f476033e17dc.tar.gz.sha256`
- `release/shanghai-commute-drive-sites.tar.gz`
- `release/shanghai-commute-drive-sites-v2.tar.gz`
- `release/shanghai-commute-drive-sites-v3.tar.gz`
- `.tooling/npm-cache`
- `.tooling/private-npm-cache`

### 保留与重建

保留 src、public、assets、backups、node_modules、references、原始设计参考、release/sites、release/open-source、GitHub CLI 和登录配置。GitHub 上的源码、8 个资源包、2 份元数据附件及备份标签不删除、不覆盖。验收浏览器配置目录和其他未列入清单的内容也保留。

现有开发依赖和运行资源仍在，继续开发使用 `npm run dev`。`npm run preview` 前需要 `npm run build`；`npm run preview:release` 前需要 `npm run build:release`。发布派生资源会由构建脚本从保留的源模型重新生成；旧 tar.gz 文件本身不再保留。本地 ZIP 已删除，需要额外恢复时按 README 从私有 Release 下载。

清理前将 release-manifest.json 和派生 runtime manifest 另存为本地审计副本，核对了 47 个原始发布输入的 SHA-256、8 个远端资源包的摘要及此前完整远端恢复证据。本轮没有重新生成大型构建产物，也没有重新发布站点。

### 清理后的验证

- 20 个目标均不存在，保留目录仍在；main 的原提交及 Sites 的提交保持一致，Sites 没有工作区或暂存区差异。
- 保留文件的路径、类型、大小和修改时间检查通过；唯一例外是 Git 状态检查自动刷新的 release/sites/.git/index 索引缓存。初次检查将其标为差异，随后用 GIT_OPTIONAL_LOCKS=0 单独核对 HEAD、工作区和暂存区，确认没有源码或提交变化。初次失败记录保留，未把它当作源文件损坏。
- 删除后重新执行可迁移回归：170/170 通过；TypeScript 类型检查通过。
- 本轮未启动、停止或重启项目服务；未重新进行浏览器或 Windows 实机验收。

本地详细记录为 `docs/private-backup/space-cleanup-approved-2026-09-11.json`、`space-cleanup-result-2026-09-11.json` 及 `.tooling/private-backup/space-cleanup-2026-09-11.log`。这些审计文件不作为运行输入，仍按仓库规则保留在本地；本报告包含远端可查阅的范围和结果。

下面保留 2026-09-10 的备份、构建与恢复记录；涉及本地 ZIP、旧下载副本及构建目录的当前状态，以本节为准。

## 本次资源范围

选中 2,024 个路径，共 6,967,439,836 字节；去重为 1,927 个对象；8 个 ZIP 合计 3,665,902,411 字节。分为 runtime、authoring、source-assets、design-references。

排除 604 个历史／临时文件路径，约 6,125,332,961 字节；这些文件只是不重复上传，仍在本地。详细范围、附件哈希及对象映射见 `asset-manifest.json`。

## 验证结果

| 项目 | 当前证据 |
| --- | --- |
| GitHub 账号 | 浏览器、连接器及官方 CLI 均确认 rttang（账号 ID 12630005） |
| 仓库私有性 | GitHub 页面显示 Private；官方 CLI API 返回 isPrivate=true / visibility=PRIVATE |
| 源码提交一致性 | 备份过程中独立克隆核对 0c422441740dfbace6c9555d32f2ecb9b2b39ca0；备份标签固定于 3bb74f203373e0f7286c610484cef63b69c7bfcd；其后 main 仅更新本报告 |
| 附件上传与远端下载哈希 | 全部 10 个附件重新从 GitHub 下载；服务器摘要、下载字节及 SHA-256 一致，1,927 个 ZIP 对象逐项解压校验通过 |
| 独立目录恢复 | 本任务专用 detached worktree 从本地附件完整恢复 2,024/2,024 个路径；逐对象和磁盘写入哈希通过 |
| 类型检查、构建、回归 | 独立目录 npm ci 成功；可迁移回归 170/170、恢复安全测试 4/4；npm run build 成功，584 个 public 文件、3,991,426,680 字节与 dist 一致 |
| 浏览器主要功能 | 恢复源码的临时 Vite 8082：自动观光、暂停／继续、接管驾驶、赏车视角、SU7 → Model 3 抽查通过；现场 warn/error 日志为空 |
| Windows 实机 | 尚未执行；2,323 个源码及资源路径的静态检查未发现大小写冲突或 Windows 禁用名称 |
| 本地清理 | 远端验证后已删除本任务恢复工作树与独立克隆目录，回收 11,881,807,872 分配字节（约 11.07 GiB）；根仓库保留 main |

## 保留边界

当前根目录最初没有 Git 仓库。已有 `release/sites` 是另一发布工作目录，本次不改变其分支或站点。未发布的 `release/open-source` 候选保留本地，不混入本次私有快照。

原始图片、模型、Blender 工程、历史备份和其他任务文件不删除。不上传 GitHub CLI 登录配置、凭据、私人聊天或内部操作日志。必要的车库动力学测量 JSON 作为运行输入保留。

## 文档

新入口为 `README.md`、`README.en.md` 和 `docs/INDEX.md`；技术方案、架构、恢复、资产来源与参考目录链接到具体文件。历史重构及发布记录继续保留，但其历史状态不能代替本次恢复验证。

## 打包完整性修复

首次逐对象解压检查发现 runtime-03 的完整街景对象压缩数据损坏。其余 7 个附件通过。当时保留首次失败记录及旧附件，生成 runtime-03-r2 新附件，并重新核对全部 8 个附件的每个对象 SHA-256。最终清单仅引用通过检查的附件。打包脚本已增加写入同步与包内成员校验；这证明本次替代包完整，不代表已确定或修复底层磁盘原因。

## 独立恢复中的补充修复

恢复目录第一次回归在资源尚未全部落盘时提前运行，因 `public/tour-city.json` 尚不存在而失败；该次日志保留，后续以资源恢复完成后的检查为准。检查构建依赖时还发现照片立面朝向 JSON 属于固定校验输入，因此补入源码清单；发布资源脚本补建自身报告目录。这些改动不调整游戏行为或绕过已有检查。

完整构建中，Vite 复制的 `skyline.glb` 和 `shanghai-streets.glb` 首次哈希与恢复后的 public 输入不同。项目原有构建校验器各重写一次，并重新核对通过。首次差异及最终通过结果保存在本地证据中。本次已确认备份包、恢复文件和最终构建副本的身份；底层复制差异的原因仍未确定。

## 验证记录与范围

源码验收基于提交 `2a30f14fbc5e4dc32cd3379ed5f868b6df1f7431`。本次只运行标准构建及上述恢复／回归／浏览器抽查，未重新生成优化发布包、未遍历完整 14 km 路线或全部车型，也未做 Windows 实机验收。另已完成独立 GitHub 源码克隆、全部远端附件内容校验和 2,024 个恢复文件重新哈希，方法见下文。之后仅更新本报告，游戏源码、验证脚本与资源清单保持与已验证快照一致。

本地内部日志位于 `.tooling/private-backup/`，包括 `local-recovery.log`、`recovery-tests-r2.tap`、`recovery-build.log` 和第一次失败记录；它们不上传到源码仓库。主要结论保存在本报告，资源身份以已跟踪的 manifest 为准。

## 远端验证方式与磁盘写入等待

源码已从 GitHub 独立克隆，并确认提交一致。首次附件下载有两个文件落盘校验成功，随后原始素材包下载长时间等待外置盘写入。当时向本任务下载进程发出停止请求，将这次下载目录移动到 `.tooling/private-backup/retained-disk-download` 保留，没有删除其内容。

后续改为逐包直接从 GitHub 下载到内存，验证下载字节数和 SHA-256，再逐项解压核对包内对象，最后重新核对已有恢复目录的全部 2,024 个文件，结果全部通过。该方式减少外置盘重复写入；独立空目录的实际恢复、构建和浏览器检查使用前文记录的本地备份包，不混称为从空目录完成的远端恢复。

下载与复制等待的底层原因尚未确定。2026-09-10 17:40 UTC 附近复查时，旧下载进程 PID 34618 仍处于系统退出等待，目录读取进程 PID 35684 仍处于内核 I/O 等待；已发送终止信号，不能宣称操作系统已回收这两个进程。相关下载副本当时已移出清理目录保留，不属于有效备份包。2026-09-11 复查时，这两个旧进程已不存在，下载副本经本轮批准删除；这不等于已确定或修复底层磁盘原因。本任务未执行磁盘修复、卸载、重挂载或强制断电。

## 服务与清理状态

| 服务 | 归属与动作 | 本轮最终状态 |
| --- | --- | --- |
| 当前项目开发／普通预览 8080 | 未启动、未停止原服务 | 检查时无监听 |
| 历史发布预览 8081 | 未启动、未停止原服务 | 检查时无监听 |
| 恢复验收 Vite 8082 | 本任务启动，PID 28576，工作目录为临时恢复工作树；验收后定向停止 | 已停止，不再提供访问 |
| 既有 Sites 站点及 release/sites | 未修改、未重新部署 | 本轮未做在线功能验证 |

2026-09-10 17:38 UTC，在远端校验通过、临时目录 Git 状态干净、未发现额外文件或符号链接后，清理了本任务的两个目录：

- `.tooling/private-recovery-check`：11,820,072,960 分配字节。
- `.tooling/private-remote-source-check`：61,734,912 分配字节。

合计回收 11,881,807,872 字节，约 11.07 GiB（11.88 GB）；同一时段文件系统空闲空间实际增加 11,882,725,376 字节，当时盘上约有 18 GiB 可用。文件系统读数可能受其他活动影响，清理规模以前述目录的分配空间为准。这是清理本次验证临时副本释放的空间，不是删除原始项目所得。

根 Git 仓库现在只保留 main 和当前工作目录，没有删除其他任务分支，也未执行全仓垃圾回收。第一轮结束时，原始项目、资产、历史备份、未发布公开候选、本地备份 ZIP 和上述失败下载副本均保留。第二轮仅删除上文批准的重复副本、构建产物和缓存，原始资源继续保留。

## 本次文件变更

- 根目录：新增 Git 跟踪／换行规则；重写中文 README，新增英文 README；保留原有产品、设计及第三方说明。
- `docs/`：新增私有文档索引、双语架构、技术方案、恢复、来源目录、同类项目参考和本报告；保留历史重构文档。原有动力学 JSON、照片立面朝向 JSON 随源码保存，满足运行和构建输入要求。
- `references/`：保留结构化地图／车型／建模参考，补入本轮许可核对记录。原资源的来源说明继续保留在资源包中。
- `scripts/` 与 `tests/`：新增分组去重打包、受校验恢复、可迁移测试入口与 4 项恢复安全测试；发布资源脚本新增报告目录创建。package.json 新增 `test:portable`，保留原始测试命令。
- `public/`、`assets/`：按清单打包并验证，没有修改或删除原始游戏资源。未引入根目录 MIT 许可证，未修改线上站点。
