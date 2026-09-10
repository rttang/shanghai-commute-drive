# 按需加载与发布优化

状态：优化版本已通过 Sites 公开部署及公网验证。

公开入口：[上海漫游 · 一江两岸](https://shanghai-commute-drive.rttang090013.chatgpt.site/)。无需登录，当前上线版本为 Sites 版本 3。本文前半部分保留本地优化阶段记录，最终部署结果见“Sites 公开部署”一节。

## 首轮本地优化范围（历史）

首页先显示；按起点和沿途加载街区；派生模型压缩；独立发布产物及缓存配置。保留原图、工程、原始模型、备份和存档格式，不发布公网，不替换 8080 服务。

## 基线

完整开发目录磁盘占用约 19.65 GiB；当前运行资源静态估算 1,044,678,164 字节；两个必载模型合计 298,223,352 字节。来源为本轮读取的代码、清单和文件大小，实际网络基线待测。原代码快照保存在 `.tooling/deployment-optimization/baseline`。

## 实施与验证

1. 原始资源哈希记录、隔离构建与网络基线。
2. 保持几何与材质的模型压缩，分离全局环境与区域道路。
3. 首页延迟加载、行进方向预加载及失败重试。
4. 发布清单、版本化资源与 HTTP 缓存。
5. 回归测试、真实浏览器网络与固定机位对比。

## 已测结果

测量环境：本机隔离 HTTP 静态服务、ARM Chrome 无头模式、1280×720、DPR 1、均衡画质。每轮使用新的浏览器配置目录；重复访问在同一轮配置中进行。时间从页面导航起算；这是本机工程样本，不代表公网或所有客户设备的速度。源数据在 `docs/evidence/deployment-optimization/*-loading.json`。

| 指标 | 原版本 | 优化版本 |
| --- | ---: | ---: |
| 首页达到可操作时累计网络传输 | 410.44 MB | 1.22 MB |
| 首页达到可操作时间 | 19.88 秒 | 0.38 秒 |
| 首次开始驾驶时累计网络传输 | 410.44 MB | 77.94 MB |
| 首次开始驾驶时间（导航起算） | 24.53 秒 | 12.33 秒 |
| 同一浏览器再次进入驾驶的实际网络传输 | 211.59 MB | 约 5.4 KB |
| 再次进入驾驶时间 | 15.20 秒 | 6.28 秒 |

重复访问仍需解析模型并建立 GPU 资源，因此命中网络缓存不等于立即进入游戏。浏览器可能清理磁盘缓存；新设备、清空缓存和新版本资源仍需下载。统计使用 Resource Timing 的 `transferSize`，其中包含 HTTP 开销；缓存命中的 `encodedBodySize` 不应再次计入真实网络流量。

最终首页流量在缩略图与背景图下载完成后统计；控件达到可操作的时间单独记录，避免漏算尚未下载完的图片。首次开始驾驶的导航总时间包含截图与自动点击等测试步骤。优化版另行测得，从点击出发到场景准备好约 10.74 秒。以上时间是单次本机样本，不能直接作为公网时延承诺。

发布文件本体合计约 **661.23 MB**。同一套文件在客户端支持 Brotli 且完整访问所有资源的情况下，压缩响应体合计约 **254.21 MB**，这不是首次访问量。目录同时附带 Brotli 和 gzip 预压缩副本，部署磁盘占用约 **1.158 GB**。客户端只请求合适的一种编码，不会把三个副本都下载。本地原始素材和备份没有删除，完整开发目录不会因本次工作变小。

## 实现方式

### 首页与车辆

首页使用原版本游戏画面截图作为轻量背景，保留现有版式。只加载界面、地图、当前座驾缩略图等资源；点击出发才开始下载三维场景。首次出发前更换车型只更新选择与缩略图，不下载精细模型。驾驶中的车型切换继续使用原有最多两辆精细车的缓存；交通车辆只预载实际用于交通的七种简模。

加载失败会保留首页并显示重试入口。重试复用已经成功加载的街区和交通模型。重复点击出发被抑制，路线与车型选择不会在尚未完成的出发请求中交叉生效。

### 街景资源

1. 沿用当前有效的 47 个街景资源作为输入，并逐文件检查原始 SHA-256；过期的派生模型不能混入构建。
2. 道路与隧道按 600 米网格分成 104 个文件，以三角形中心归属分区，但保留整片三角形及原始顶点属性；不裁切、不移动顶点。每个分区按实际几何边界决定加载距离。
3. 地面、江面和远处建筑轮廓维持常驻，避免道路分块后地平线缺失；天际线保持完整几何。
4. 对普通几何使用无损 Meshopt 缓冲区压缩，编码后逐字节解压比对。不降低贴图分辨率、不重新编码图片、不简化网格、不量化顶点。已有 Draco 资源保留原格式。Meshopt 支持精确保存顶点与索引数据，使用方式参考 [Khronos 扩展规范](https://raw.githubusercontent.com/KhronosGroup/glTF/main/extensions/2.0/Vendor/EXT_meshopt_compression/README.md)。
5. 将可共享的内嵌贴图按内容哈希保存为独立文件，保留原图字节。多个分块引用同一 URL，便于浏览器缓存复用。最终有 150 个街景分块。
6. 当前可见范围优先于前方预加载；根据车速、朝向和巡游倍率预取前方约八秒、最多 400 米的区域。转向后不再请求过期队列，远处分区释放资源。卸载时一并清理应用对隧道网格的引用。

### 发布与缓存

普通 `npm run build` 保留原开发流程。新增独立发布构建，避免原来的全量 `public` 复制与补齐校验把历史文件重新带入产物。

```sh
npm run build:release
# 原模型未变，只更新代码时可复用已经验证的派生模型：
npm run build:release -- --reuse-assets
npm run test:release
npm run pack:release
npm run preview:release
```

输出为项目根目录的 `dist-release`；预览地址为 `http://127.0.0.1:8081/`。端口被占用时启动失败，不结束或替换已有进程。派生模型保存在 `.tooling/deployment-optimization/runtime-assets`，构建检查输入哈希并只复制清单实际引用的文件，不把该目录中的历史派生副本一并发布。

| 文件类别 | HTTP 缓存策略 |
| --- | --- |
| HTML、地图、运行清单、使用固定名称的车辆文件 | `no-cache`，使用 ETag 重新验证；内容未变返回 304 |
| `/runtime/<内容哈希>/...` 街景与共享贴图 | 一年缓存，`immutable` |
| Vite 生成的带哈希 JS/CSS | 一年缓存，`immutable` |
| 可压缩文件 | 根据 `Accept-Encoding` 选择 `.br`、`.gz` 或原文件，返回正确的 `Content-Encoding` 与 `Vary` |

上线时上传发布目录，保留 URL 目录结构，配置 HTTPS 与相同缓存策略。不要把整个项目目录、`node_modules` 或 Vite 开发服务器公开。HTML 和运行清单不能设置永久缓存；更新时先上传新哈希资源，再切换入口及清单，旧哈希资源应继续保留一段时间，供已打开旧页面的客户使用。

若使用 Nginx，预压缩 gzip 文件需要服务器包含 `ngx_http_gzip_static_module` 并启用 `gzip_static on`；该模块并非默认编译模块。Brotli 的实际传输效果也依赖托管平台的编码支持。本轮预览服务器已实现两种编码协商，参考 [Nginx 预压缩文件说明](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)。本轮未连接云平台、配置域名或发布公网。

## 验证记录

- 优化前 171 项现有测试通过；新增加载与释放测试后，173 项基础测试通过，无失败或跳过。
- 4 项发布资产检查通过，覆盖原始 SHA-256、共享贴图、无损解码、道路分区三角形、HTTP 缓存、发布文件及两种编码的解压一致性。许可证补齐后又重跑了最终文件与编码完整性检查。
- 原照片立面朝向与道路净空检查通过，证据仍写入项目既有 `street-master-photo-placement.json`。
- 浏览器已验证首页和出发前换车不下载 GLB；注入一次 503 后可以直接重试；10 款车型切换正常且每辆都有四个独立车轮；手动油门可移动车辆并带动车轮；手机宽度保留出发入口。
- 当前可选的约 14.06 公里上海环线完成一整圈并实际跨过接缝；圈数为 1，里程计约 14.08 公里，测试巡游约 618 秒。全程未出现模型、贴图加载失败或浏览器错误。证据为 `browser-regression.json`；它使用真实动画循环和现有诊断页，没有通过浏览器脚本修改驾驶状态或虚构时钟。
- 外滩和浦东均使用原版与优化版相同的路线、600 米距离、驾驶舱机位及分辨率。浦东 921,600 个像素完全一致；外滩 2,851 个像素有差异，占约 0.309%，RGB 通道平均绝对差约 0.0080/255。已查看对照图，未见明显画质退化。该结论仅覆盖已比较的机位，不代表逐像素覆盖所有路线。
- 第一轮浏览器检查暴露了共享贴图路径重复拼接问题，已改为绝对模型 URL 后通过；失败证据保留在 `optimized-loading-failed-shared-textures.json`，没有以成功结果覆盖它。
- 当前项目不是 Git 仓库，没有创建提交。本轮由主 agent 实施与复核；跨会话子任务占用无法完整核实，因此没有新增 subagent，也没有独立 agent 审查。

## 本轮文件变更

| 文件 | 新增、替换或删除内容 |
| --- | --- |
| `src/main.ts` | 将三维资源加载移到出发阶段；新增准备状态、重试和出发前车型选择；替换首页启动顺序 |
| `src/tour/ui.ts` | 新增准备与失败重试界面，复用现有样式 |
| `src/style.css`、`public/home-preview.jpg` | 新增原游戏画面的轻量首页预览 |
| `src/tour/world.ts` | 新增 Meshopt 解码、发布清单选择、可重试加载、实际交通车型预载、前方预测和卸载引用清理 |
| `src/tour/street-streaming.ts` | 新增前方预加载队列与卸载回调；保留当前位置优先和加载半径策略 |
| `scripts/lib/release-glb.mjs`、`scripts/lib/split-context.mjs` | 新增无损缓冲区编码、解码校验和道路分区工具 |
| `scripts/build-release-assets.mjs`、`scripts/build-release.mjs` | 新增源哈希校验、共享贴图、版本化资源、发布白名单和预压缩构建 |
| `scripts/serve-release.mjs` | 新增隔离静态预览、编码协商及缓存验证 |
| `scripts/pack_release.py` | 新增可复现的发布压缩包生成、包内逐文件哈希校验和校验和文件 |
| `scripts/measure-loading.mjs`、`scripts/verify-release-browser.mjs` | 新增冷、热访问测量及交互与环线浏览器回归 |
| `src/streets-review.ts` | 为现有诊断页新增行驶里程、圈数和跨过环线接缝后的停止条件，仅用于验收 |
| `tests/street-streaming.test.ts`、`tests/release-assets.test.mjs` | 新增前方预加载、释放顺序、资源与缓存验证 |
| `package.json`、`package-lock.json`、`vite.config.ts` | 新增发布入口与明确的 Meshopt 依赖；增加独立发布构建分支 |
| 本报告及 `docs/evidence/deployment-optimization` | 新增基线、成功及失败证据、资源清单、截图与测量结果 |
| `README.md` | 新增独立发布、验证和本地预览入口 |
| `THIRD_PARTY_NOTICES.md` | 追加本轮新增运行时解码器 meshoptimizer 1.1.1 的完整 MIT 许可证 |

没有删除原始模型、工程、图片或历史备份。开发和验收生成的新增文件也留在本项目内。

## 最终交付

- [发布压缩包](../release/shanghai-commute-drive-9af5f476033e17dc.tar.gz)：757,722,029 字节，约 758 MB；包内 575 个文件逐一通过校验，包括 Brotli 与 gzip 副本。
- [压缩包 SHA-256](../release/shanghai-commute-drive-9af5f476033e17dc.tar.gz.sha256)：`d15cafede5917fcbde7af53774e2b6de9d5489932dd4d432c93de1a3d5afe82c`。
- [发布清单](../dist-release/release-manifest.json)：SHA-256 为 `9af5f476033e17dc3b895a8408d13311b581b850ec5051bb346d8585a719a2cf`。
- [优化版预览](http://127.0.0.1:8081/)：可访问，已校验当前服务的发布清单与压缩包一致。

压缩包同时包含原文件和两种 HTTP 编码副本，所以它会大于单独应用 Brotli 后的全量传输体积。解压后直接部署其中的 `dist-release` 目录即可保留本轮测试使用的资源结构。

完整浏览器回归对应的发布清单 SHA-256 是 `3361912ad4025b96edcf1e14cfe15cb51f50506dce47ca6a9321f6c3b48b4ab5`；之后仅补齐了许可证文字，所有 HTML、JavaScript、模型和贴图的哈希均未变化。最终包又经过逐文件校验。差异证明保存在 `final-artifact-compatibility.json`，避免把不同产物笼统视为同一次浏览器验证。

## 服务清单与边界

| 服务 | 用途/组件 | 归属 | 最终状态 | 端口/PID | URL | 就绪或验证结果 | 本轮动作 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 优化版预览 | 发布产物 / Node 静态服务 | 本轮启动 | RUNNING | 8081 / 25605 | http://127.0.0.1:8081/ | 页面、150 分块清单及包版本匹配 | 更新许可证后重启本轮进程，保留运行 |
| 原开发服务 | 源码 / Vite | 原有 | STOPPED | 8080 / 原 PID 9354 | 不可访问 | 最后复查无监听，原 PID 已退出 | 本轮未停止或重启该进程；退出原因未确认 |
| 浏览器验收 | 隔离静态服务 / Node | 本轮启动 | STOPPED | 8082 / 原 PID 23423 | — | 完整环线与交互通过 | 浏览器与服务均已关闭 |
| HTTP 缓存检查 | 临时 HTTP 服务 / Node | 本轮启动 | STOPPED | 50510 / 原 PID 23451 | — | 缓存与条件请求通过 | 测试后关闭 |

最终盘点没有发现其他本项目监听服务。进程工作目录、端口、就绪与关闭证据在 `service-inventory.json`、`service-ownership-verification.json`、`final-readiness.json` 及相应测试记录中。

原 8080 服务在较早检查时正常，最后复查时已退出。本轮只重启了自己启动的 8081 预览进程，没有向原 PID 9354 发送停止指令，也没有擅自重新启动 8080。最终状态与检查证据单独保存在 `original-service-exit.json`。

8081 与 8080 是不同浏览器源，进度存储彼此独立；本轮没有迁移或清空原进度。手机仅做了 390×844 宽度的布局检查，未做手机实机验证；公网、CDN、真实客户网络及多设备帧率尚未验证。本轮完成的是本地工程与浏览器验证，不包含上线发布或客户验收。

<!-- sites-deployment-start -->
## Sites 公开部署（2026-09-10）

用户另行批准：将优化版本公开发布到 Sites，适配大文件及缓存，使用独立发布目录和必要的 Git 提交、推送，验证匿名访问及驾驶流程；保留原始工程、素材和现有本地服务。此前章节记录的是本地优化阶段，当前公开发布状态以本节为准。

当前状态：Sites 版本 3 已成功公开上线，并通过匿名资源检查及浏览器驾驶验证。公开入口为 https://shanghai-commute-drive.rttang090013.chatgpt.site/，最终推送提交为 `cff0c5ac0a243f82b419cb005ef03d52b27dbfad`；前两个失败版本的记录保留。最终线上内容来自该提交的远端构建，本地核验包未被错误记为上传成功。

### 托管适配

- 独立发布目录：`release/sites`。主项目目录仍不初始化 Git；Sites 所需 Git 仅存在于独立发布目录。
- 原始 `dist-release` 保留。209 个运行文件经 gzip/identity 传输后的字节均与原发布清单 SHA-256 一致，不修改 HTML、JavaScript、模型或贴图内容。
- 选择 gzip 作为公开托管的预压缩编码；不接受 gzip 的客户端通过服务端流式解压获得原始内容。全量资源压缩响应体合计 276,596,654 字节，实际去重上传片段 276,521,448 字节；这不是首页或首次驾驶的下载量。
- 压缩内容分成最多 8 MiB 的片段，实际上传 221 个去重片段，低于 Workers 静态资源的 25 MiB 单文件限制。[Cloudflare 限制](https://developers.cloudflare.com/workers/platform/limits/)
- Worker 保留原资源路径，逐片返回响应；内容哈希 URL 使用一年缓存，入口及清单要求重新验证，返回 ETag 和 Vary。使用原始客户端 Accept-Encoding，避免 Cloudflare 规范化请求头影响协商，并加 no-transform 保留预压缩响应。[Cloudflare 请求头](https://developers.cloudflare.com/fundamentals/reference/http-headers/)
- 使用 FixedLengthStream 输出准确长度，不把完整大模型读入 Worker 内存。[Cloudflare Response](https://developers.cloudflare.com/workers/runtime-apis/response/)

### 本地验证与独立复核

- 所有 209 个文件、418 种编码表示校验通过；HEAD、ETag 304、缓存、编码协商、404/405/502 检查通过。
- 一个独立只读 subagent 审查发现并复验了分片切换时取消下载的竞态修复；同时复核固定长度流和构建输出旧文件清理。未让 subagent 创建站点、获取凭据、编辑发布目录或部署。
- 第一次源码上传返回 HTTP 403，当时临时上传凭据已过期；没有把 `Everything up-to-date` 尾行当作成功。刷新同一站点上传授权后确认远端没有分支，重新上传。
- 第二次大包上传发生 TLS 连接中断，随后确认远端仍无分支。改为每批不超过 24 MiB 的 12 次增量上传，每批独立确认；仅对本次 Git 命令指定 HTTP/1.1 与 32 MiB 缓冲，不修改全局网络或 Git 配置。原准备提交保留在本地 `codex/build/sites-prepared-snapshot`，最终源码树与其逐项一致。
- 12 批增量上传均以退出码 0 完成。成功推送后重新读取 HEAD：`36d2e2b3854f0705fa89861a560aac63b91f21b7`，工作区干净。部署包由同一源码树生成，归档 224 个文件均与构建输出及源托管配置一致，没有多余文件。
- Sites 部署包：`release/shanghai-commute-drive-sites.tar.gz`，269,692,227 字节；SHA-256：`1825311090994998b6546c1d3b6f97932febc96ed80d9c2305cbbd019e464d26`。
- 本地部署包已成功生成，但原生文件上传接口在 60,001 ms 处超时，包未提交给 Sites。确认没有创建任何版本后，改为保存同一已推送提交的源码版本，使用平台远端构建。没有将本地包校验冒充服务端已接收包的证据。
- 版本 1 的远端构建明确返回输入归档 256 MiB 上限；核算 Git 源码 tar.gz 为 269,685,775 字节，上限为 268,435,456 字节。失败记录保存在 `sites-deployment-v1-failed.json`。
- 对两个最大模型采用 Zopfli 的标准 gzip 编码，共减少 2,858,544 字节；原始模型字节完全相同，运行端不增加解码库。原压缩分片转存本地 `.tooling/deployment-optimization/sites-v1-parts`，原始 `dist-release` 不变。[Zopfli 官方项目](https://github.com/google/zopfli)
- 修正后的源码 tar.gz：266,736,347 字节（约 254.4 MiB），低于 256 MiB 输入上限；本地核验包 `release/shanghai-commute-drive-sites-v2.tar.gz` 为 266,742,903 字节，SHA-256 为 `cb3bf494643550c0df476833c745d389170e25068a60363c273d35d05f3297be`。包内 224 个文件全部验证通过，209 个原文件的 418 种传输表示再次校验通过。
- 修正后全量压缩响应体合计为 273,738,110 字节，去重片段实际占用为 273,662,904 字节；均不代表首页或首次驾驶下载量。`sites-archive-v2.json` 和 `sites-zopfli-applied.json` 记录最终大小及解压一致性。
- 版本 2 通过压缩包大小检查后，又触及 256 MiB 的解包大小限制。最终对 13 个存储片段增加 gzip 存储层，减少 6,339,081 字节；Worker 逐片流式还原这一层，浏览器接收的 HTTP 表示和原始资源不变。旧片段转存 `.tooling/deployment-optimization/sites-before-wrapping`。
- 最终存储片段共 267,323,823 字节。本地核验包 `release/shanghai-commute-drive-sites-v3.tar.gz` 为 266,868,385 字节，解包 tar 为 267,675,136 字节；源码归档压缩后为 266,862,652 字节，展开后为 267,683,840 字节。四项均低于 268,435,456 字节（256 MiB）。
- 最终核验包 SHA-256：`8d1dd835a33d2da084d48e7b45c8248afecbd4810e84b0fda1bc0d868a9cd474`。`sites-archive-final.json` 覆盖全部 224 个归档文件、两类归档的压缩与解包上限，以及最终源码提交。全部 418 种资源传输表示再次校验通过，增加了取消存储压缩流后的源流关闭检查。
- 本地验证不代替公网、CDN 或真实客户验收。

### 公网验证与交付

- 发布状态为 `succeeded`，访问权限复查为 `public`，当前线上版本为 3。站点、版本、部署记录及提交对应关系见 `sites-deployment.json`。
- 不携带登录 Cookie 或授权头的 HTTP 检查覆盖全部 209 个运行文件：均返回成功，解压后的 SHA-256 与优化版一致。gzip、清单的 identity 响应、ETag 304、入口重新验证、内容哈希资源一年缓存以及不存在资源的 404 均通过。完整记录见 `sites-resources.json`。
- 内置浏览器首页已正常显示，点击出发前 `sceneReady=false`，GLB 请求数为 0。该次首页资源传输为 1,276,224 字节，加主文档 840 字节，共约 **1.28 MB**。这是一次浏览器样本，不代表所有设备、网络或缓存状态。
- 已进入自动观光并看到真实三维街景、车辆、路面、树木及地图；随后切换到手动驾驶，界面显示手动驾驶及油门、刹车、转向控制。测试行驶约 1.10 km 后主动暂停，`sceneReady=true`，已加载 16 个分块，无失败分块，浏览器错误日志为空。
- 网络事件缓冲区出现过截断，因此没有把浏览器事件缓冲当作全量请求证据；全量网络结论来自独立的 209 文件 HTTP 校验。浏览器记录见 `sites-browser.json`。本次同时进行全量资源下载核验，没有记录可用于比较的首开耗时。
- 最后复查时，使用 `Python-urllib/3.13` 标识的首页请求收到 Cloudflare 403；默认 Node 客户端的 gzip、identity 请求和浏览器访问均正常。这一客户端差异单独记录在 `sites-final-access.json`，没有通过更改平台安全配置处理它。
- 预览标签已标记保留，停在可继续行程的驾驶画面。向 Codex 侧栏展示该标签的请求返回 `queued`，不把它记为已切换到用户当前前台窗口。
- 本次线上检查覆盖首页、约 1.10 km 驾驶、手动接管与暂停；未在线上重新跑完整环线，也未做手机实机、多地区网络或并发压力测试。此前完整环线证据仍属于本地验证。
- 一项独立只读审查子任务已完成，当前任务树没有仍在执行的子任务。历史子任务没有归档，运行时未提供关闭接口，因此没有声称已关闭历史线程。

### 最终服务状态

| 服务 | 用途/组件 | 归属 | 状态 | 端口/PID | 入口 | 就绪证据 | 本次动作 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sites 公开站点 | 上海驾驶 / Workers | 本次创建 | RUNNING | 443 / 平台管理 | [公开入口](https://shanghai-commute-drive.rttang090013.chatgpt.site/) | public、版本 3、209 文件校验及浏览器驾驶通过 | 部署并公开 |
| 优化版本地预览 | 发布产物 / Node | 已存在 | RUNNING | 8081 / 39996 | [本地预览](http://127.0.0.1:8081/) | 150 个分块、delivery=true，原优化发布清单 SHA-256 匹配 | 保留运行 |
| 原开发服务 | 源码 / Vite | 已存在 | NOT_STARTED | 8080 / — | 不可访问 | 无监听 | 未操作 |
| 此前验收服务 | 本地测试 / Node | 前一阶段 | STOPPED | 8082 / — | — | 已停止，本次未启动 | 未操作 |

本次没有重启或停止任何本地服务。最终发现的项目监听服务与预期一致；本地运行进程归属及就绪检查见 `sites-service-inventory.json`。本地 8081 仍使用原始已验证的优化产物，发布清单 SHA-256 为 `9af5f476033e17dc3b895a8408d13311b581b850ec5051bb346d8585a719a2cf`。

后续增加资源前须重新运行 `scripts/verify-sites-package.py`：当前源码展开后的体积距平台上限约 0.72 MiB。此限制针对发布归档，不等于客户首屏下载量。

### 本次新增文件

| 文件 | 新增内容 |
| --- | --- |
| `scripts/prepare-sites-release.mjs` | 从原发布清单校验并生成 gzip 分片、路径映射与证据 |
| `scripts/verify-sites-resources.mjs` | 匿名校验线上所有资源的 SHA-256、编码和缓存 |
| `scripts/verify-sites-package.py` | 校验源归档和部署归档的压缩/展开上限、文件白名单与哈希 |
| `release/sites/source/worker.mjs`、`source/asset-index.json`、`source/assets/` | 流式托管适配及已验证运行资源 |
| `release/sites/build.mjs`、`verify.mjs` | Worker 构建与逐文件传输校验 |
| `release/sites/.openai/hosting.json`、`.gitignore`、`package.json`、`README.md` | 独立发布配置与说明 |
| 本报告、`docs/evidence/deployment-optimization/sites-*` | 当前发布状态、资源校验及服务记录 |

未删除或替换原始素材、原发布包、驾驶源码及本地服务。
<!-- sites-deployment-end -->
