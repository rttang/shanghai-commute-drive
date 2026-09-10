# 浦东连续环线建筑照片与模型证据

更新：2026-09-09T13:23:44.707914+00:00

连续环线 5800—9260 米范围共有 **57 个首排建筑分体**，当前几何覆盖 **57/57**。其中 **35 个分体没有可直接对应的已查看外景照片**。地图覆盖不等于照片还原验收。

浦东区保留及新增模型共 108 个，覆盖 113 个地图分体；GLB 合计 437,546,128 字节，7,659,897 个三角形。已逐件验证 SHA-256、GLB 文件头及声明体积。

## 本次主要修正

- 候选集补入连续环线首排目录，修复只读旧浦东路线而遗漏 21 个分体的问题。
- 上海银行：实拍支持石材侧翼、中央凹进玻璃、内凹冠部和双天线；另建西北低裙房，其入口和立面仍未获直接实拍支持。丹下图库两张效果图已排除。
- 中银大厦：依据日建外景和入口照片，建立弧形塔身、斜切下部、开放冠部、侧天线与弧形玻璃入口。主体高度 226.1 米，最高尖部 258 米。
- 交银金融大厦：依据两张街面照片及一张金茂俯拍，建立高低双薄板塔楼、斜切玻璃屋顶、退进玻璃连接体、水平挑檐、端墙和圆形低附楼。北楼约 230.4 米，南楼约 198 米，尖部 265 米。
- 陈桂春住宅：采用明确标注的照片比例高度估计；山墙位于屋脊端部，木格栅立面与白灰背墙分开，保留两处院落。
- Disney：钟塔移回店前凹形广场，补下部拱门、挑檐及开放柱廊；人物雕像与机械动画没有建模。
- 金茂与环球裙楼入口从最终 GLB 回读。环球补准确特写，黑框、SWFC 字牌和三组旋转门可见；旋转门已改用半透明玻璃，其余玻璃反射和未建模室内仍影响真实感。

## 资料与验证边界

- 原始照片和既有模型保留，覆盖前备份并核对哈希；无授权照片未嵌入运行时纹理。
- 本次参考登记共 76 项，可用于建筑几何的已查看实拍 61 项。无关社区泛景、地图、室内和广告另列排除清单。
- 新增无名建筑保留地图平面及显式高度来源，其立面划分、材质和入口为推断，不得称为高保真实景完成。
- photoVerified 仅表示每个组成分体存在直接对应、已查看的外景照片；realPhotoAcceptance 仍为 false。
- 模型回读不能替代整条路线的浏览器验收、服务检查及全街景 5 GB 预算核查。

## 连续环线逐分体清单

| 路线里程（米） | Way | 建筑 | 模型 | 照片证据 |
| ---: | --- | --- | --- | --- |
| 5809.5 | 965047353 | OSM building 965047353 | pudong-way-965047353 | 未核实 |
| 6072.2 | 957451688 | 自由贸易试验区览海国际广场 | pudong-way-957451688 | lanhai-street |
| 6073.2 | 165591946 | OSM building 165591946 | pudong-way-165591946 | lanhai-street, swfc-entrance-traveler |
| 6275.1 | 415667888 | OSM building 415667888 | pudong-way-415667888 | 未核实 |
| 6284.3 | 957456631 | OSM building 957456631 | pudong-way-957456631 | 未核实 |
| 6312.6 | -128762950 | OSM building -128762950 | pudong-way-r128762950 | 未核实 |
| 6321.2 | -128762951 | OSM building -128762951 | pudong-way-r128762951 | 未核实 |
| 6332.0 | 415667808 | OSM building 415667808 | pudong-way-415667808 | 未核实 |
| 6370.7 | 957456630 | OSM building 957456630 | pudong-way-957456630 | 未核实 |
| 6443.3 | 948045836 | OSM building 948045836 | pudong-way-948045836 | 未核实 |
| 6455.1 | 957451695 | OSM building 957451695 | pudong-way-957451695 | 未核实 |
| 6465.6 | 956369950 | OSM building 956369950 | pudong-way-956369950 | 未核实 |
| 6467.8 | 956369947 | OSM building 956369947 | pudong-way-956369947 | 未核实 |
| 6491.3 | 956369949 | OSM building 956369949 | pudong-way-956369949 | 未核实 |
| 6493.5 | 956369946 | OSM building 956369946 | pudong-way-956369946 | 未核实 |
| 6517.5 | 956369945 | OSM building 956369945 | pudong-way-956369945 | 未核实 |
| 6521.4 | 956369948 | OSM building 956369948 | pudong-way-956369948 | 未核实 |
| 6546.3 | 956369951 | OSM building 956369951 | pudong-way-956369951 | 未核实 |
| 6564.3 | 957451684 | OSM building 957451684 | pudong-way-957451684 | 未核实 |
| 6578.4 | 957451686 | OSM building 957451686 | pudong-way-957451686 | 未核实 |
| 6592.1 | 957451683 | OSM building 957451683 | pudong-way-957451683 | 未核实 |
| 7102.8 | 164972436 | 招商局大厦 | pudong-way-164972436 | lujiazui-insurance-merchants, merchants-full, park-2022-1, park-2024-39 |
| 7166.6 | -129813030 | 世界金融大厦 | pudong-way-r129813030 | world-finance-full, park-2024-39 |
| 7166.6 | -129813031 | 世界金融大厦 | pudong-way-r129813031 | world-finance-full, park-2024-39 |
| 7217.3 | 165168179 | OSM building 165168179 | pudong-way-165168179 | 未核实 |
| 7244.6 | 165168178 | OSM building 165168178 | pudong-way-165168178 | 未核实 |
| 7309.8 | 166545281 | OSM building 166545281 | pudong-way-166545281 | 未核实 |
| 7311.7 | -129813020 | 华能联合大厦 | pudong-way-r129813020 | huaneng-full |
| 7393.9 | -129813072 | 恒生银行大厦 | hang-seng | hang-seng-original-rechecked |
| 7425.0 | -129813071 | 恒生银行大厦 | hang-seng | hang-seng-original-rechecked |
| 7435.0 | -129813070 | 恒生银行大厦 | hang-seng | 未核实 |
| 7584.4 | 164903482 | 黄金置地大厦 | pudong-way-164903482 | golden-bank-shanghai |
| 7685.8 | 166544770 | OSM building 166544770 | pudong-way-166544770 | 未核实 |
| 7728.3 | -129809231 | 上海银行大厦 | pudong-way-r129809231 | bank-shanghai-architect-1, bank-shanghai-architect-2 |
| 7730.0 | 164957811 | 中银大厦 | pudong-way-164957811 | boc-architect-2, boc-architect-3, boc-architect-4, boc-architect-5, boc-architect-6, boc-architect-7 |
| 7798.5 | -129809230 | 上海银行大厦 | pudong-way-r129809231 | 未核实 |
| 7815.8 | 164971470 | 交银金融大厦 | pudong-way-164971470 | bocom-close, bocom-full, bocom-aerial |
| 7860.9 | -129809240 | 汇亚大厦 | pudong-way-r129809240 | azia-02, azia-03, azia-04 |
| 7861.0 | 965004773 | OSM building 965004773 | pudong-way-965004773 | 未核实 |
| 7990.3 | 1533181378 | 上海海洋水族馆管理楼 | ocean-aquarium | 未核实 |
| 7996.2 | 520990201 | 中国平安金融大厦 | pudong-way-520990201 | pingan-bank-3 |
| 8065.3 | 404676268 | 上海海洋水族馆 | ocean-aquarium | aquarium-owner |
| 8173.7 | 165168434 | OSM building 165168434 | pudong-way-165168434 | 未核实 |
| 8201.8 | 166125932 | OSM building 166125932 | pudong-way-166125932 | 未核实 |
| 8224.4 | 1211163026 | OSM building 1211163026 | pudong-way-1211163026 | 未核实 |
| 8229.5 | 166125926 | OSM building 166125926 | pudong-way-166125926 | 未核实 |
| 8314.5 | 1211163027 | OSM building 1211163027 | pudong-way-1211163027 | 未核实 |
| 8361.0 | 427786590 | 迪士尼旗舰店 | pudong-way-427786590 | disney-clock, disney-clock-detail, disney-store-01, disney-store-02, disney-store-04 |
| 8385.0 | 40779113 | 正大广场 | super-brand-mall | super-brand-original-rechecked |
| 8500.3 | 255624910 | Apple 浦东 | apple-pudong | ifc-apple |
| 8549.1 | 160165834 | OSM building 160165834 | pudong-way-160165834 | 未核实 |
| 8596.0 | 423304682 | 国金中心二期 | ifc-south | ifc-apple |
| 8648.8 | 526005642 | 上海国金中心商场 | pudong-way-526005642 | ifc-apple |
| 8822.2 | 961656405 | OSM building 961656405 | pudong-way-961656405 | 未核实 |
| 8888.4 | 167061959 | OSM building 167061959 | pudong-way-167061959 | 未核实 |
| 8957.9 | 376075961 | 金茂大厦 | jinmao | jinmao-front, jinmao-detail, jinmao-owner-0, jinmao-owner-1, jinmao-owner-2, jinmao-owner-3, jinmao-owner-4, jinmao-owner-5, jinmao-owner-6, jinmao-owner-7, jinmao-owner-8, jinmao-owner-9, jinmao-entrance-traveler |
| 9041.8 | 165168180 | 陈桂春住宅 | pudong-way-165168180 | chen-mansion, chen-traveler-0, chen-traveler-5, chen-traveler-6 |

## 输出与复核入口

- 结构化证据：`references/tourism/pudong-loop-building-evidence.json`
- 照片登记：`references/tourism/pudong-loop-photos.json`
- 排除资料：`references/tourism/pudong-loop-reference-rejections.json`
- 模型清单：`public/streets/districts/pudong/manifest.json`
- 回读图片：`public/streets/districts/pudong/review/`
- 可编辑场景：`assets/blender/streets/pudong-detailed.blend`

最终回读：22 个本轮新增或修改模型均从最终 GLB 渲染三视图并逐图查看；浏览器页面错误为 0。金茂入口另已回读。记录见 `references/tourism/pudong-loop-manual-review.json`。先前发现的中银顶面和陈桂春窗格问题已保留首轮记录，并完成修正回读。
