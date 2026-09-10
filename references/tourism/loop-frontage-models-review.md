# 浦西新增环线临街建筑补完记录

本轮仍未达到41个目标way全部按真实照片补完的要求。当前16栋照片专属模型已经导出并完成GLB回读；已看过全部前、后、侧俯视图，发现的问题正在按受影响ID增量修复。25个way尚无可精确匹配的临街照片，继续保留原有楼体与碰撞，`replacesWays`全部为空。

## 本轮新增内容

- 外滩瑞吉：对照建筑师带标尺北立面、北区平面、航拍以及更名后的酒店照片，制作前低后高体量、花岗石外框、铜色窗竖框、西北入口雨棚与旋转门、ST REGIS字样。
- BFC临江长楼：对照建筑师北区平面及航拍，制作四段不同檐高、石材外框、双层高店面框架；OSM的N3编号与建筑师酒店N3编号不一致，记录编号歧义，不标成酒店。
- RIVIERA松鹤楼：保留两层主体与退台屋顶餐厅，制作独立窗框、入口台阶、坡道栏杆、临江招牌和屋顶棚架。首次回读发现短共线边重复招牌、分格过于平均、石材拼缝跨过玻璃；已修复，并重新读取临江、道路、后侧和侧俯视图。
- 丹凤楼一尺花园：通过品牌官方建筑照片、PICC及BFC背景、独立入口照片和弯折轮廓匹配OSM旧称高博金融家俱乐部的建筑，制作架空红钢框、玻璃廊、下层圆弧灰砖房、圆窗、外楼梯及屋顶缆索栏。
- 古城公园8号门公厕：政务园区图把厕所定位在西北角，正立面照片显示灰砖、低瓦顶、黑色窗楣、钢制双门、铁栅气窗、打开的高窗和333门牌。没有将同一照片套到东南角公厕。
- 接续前代理已写但未导出的福佑商厦、紫锦城专属builder；悦园瓦脊分段修复在本轮重新生成。

## 证据与使用边界

- [BFC建筑师提供的项目照片、平面与立面](https://www.archdaily.com/881511/bund-finance-centre-foster-plus-partners-plus-heatherwick-studio)：本轮读取了航拍、北区首层平面、酒店首层平面及酒店北立面。
- [Foster + Partners项目说明](https://www.fosterandpartners.com/projects/bund-finance-center/)：用于核对石材和铜色金属构造，未作为具体楼号的独立证明。
- [万豪官方酒店资料](https://www.marriott.com.cn/hotels/shaxb-the-st-regis-on-the-bund-shanghai/overview/)与[当前携程酒店照片](https://hotels.ctrip.com/hotels/4889292.html)：核对酒店身份及更名后的ST REGIS字样；万豪图片直链返回403，未把下载失败记为已归档。
- [松鹤楼临江立面](https://www.smartshanghai.com/listings/dining/good-view/)与[入口角部照片](https://touch.travel.qunar.com/comment/10161212455)。
- [一尺花园官方建筑照片](https://www.yichizhijian.com/NewsDetail/3769341.html)与[独立入口照片](https://blog.livedoor.jp/camsa/archives/5903985.html)。商家地址和旧OSM名称存在时效差异，模型保留说明。
- [古城公园政务公告与8号门公厕照片](https://www.thepaper.cn/newsDetail_forward_27956883)：地图用于定位，建筑照片用于立面。

无许可照片只归档、观察和重建几何，不作为运行时材质。所有原下载文件保留；照片台账记录来源、用途、字节数和SHA-256。没有把历史工地或道路绿化报道当成具体建筑拆除证据。当前尺度来自OSM、建筑师图和照片比例，未作实测；隐藏后立面明确标为推定。

## 当前验证状态

当前16个运行时模型合计90.580MB，平均5.661MB。悦园约15.76MB、紫锦城约16.12MB、全季约10.50MB；模型平均低于10MB要求，未通过降面或压缩掩盖几何变化。具体数字以最终manifest为准。

- 每栋GLB重新导入Blender，比较导出前后几何包围盒；差值阈值0.02m。
- 本轮逐栋产生前、后、侧俯视图；部分入口和临江方向另有视图。源图与回读图逐张核对，图片不等于最终照片保真验收。
- 初始运行时模型、blend、脚本和配置保存在`assets/streets/loop-frontages/preserved/20260909-152750/`；后续覆写按SHA保存，旧复核图另有逐图SHA副本。
- 改进增量`--ids`构建：读取已有blend并仅替换目标对象，manifest保留其他已导出模型，避免补一栋导致其余模型从manifest消失。
- 初轮15个模型导出后，先核验GLB哈希及blend完整，再在PNG写完后停止后续Cycles循环，释放共享队列。后续低采样EEVEE只重绘修改或缺失的视角，未压缩几何或材质。
- 钱业公所牌匾缺字：直接加载Songti.ttc时Blender选择第0字面Black，该字面缺「業、錢、滬」；已取本机第6字面Songti SC Regular生成本地建模用字体，验证字形编号及SFNT校验和，最终GLB牌匾已无缺字框。原照片从右向左题字的顺序保留。
- 瑞吉临江招牌镜像：纠正自定义切线和法向形成左手坐标基的问题，最终回读字样为正常方向。
- 后续俯视检查发现NEO、悦园、上海滩商厦退台楼面缺面，以及坡屋顶端墙未封闭；已补楼板、山墙并保留NEO天井。公厕按真实入口短边重做完整双坡屋顶；紫锦城大面板下方补独立入口。当前等待该局部修复批次最终回读。
- 最终只对新增公厕和圆顶楼深色瓦补2张Cycles关键材质图，其他视角以实际GLB的EEVEE及已有Cycles图交叉核验。完成后须刷新哈希、图像清单与进程退出状态。

## 未通过项

25个目标way没有建筑级立面证据，未导出臆测模板来填数量；当前所有模型的`photoFidelityAccepted`仍为false。全部目标补完及整场景道路遮挡、碰撞和用户视觉验收由主任务继续。逐栋清单以配置、inventory及运行时manifest为准。

## 逐栋生成清单


| 名称 / OSM way | 路线里程m | 专属几何 | 已导出MB |
|---|---:|---|---:|
| OSM building 447021392 / [447021392](https://www.openstreetmap.org/way/447021392) | 1507.0 | provisional | — |
| RIVIERA松鹤楼（中山东二路505号） / [515758765](https://www.openstreetmap.org/way/515758765) | 1940.1 | riviera | 1.836 |
| BFC北区临江商业办公长楼（OSM标注N3） / [447024815](https://www.openstreetmap.org/way/447024815) | 1968.9 | bfc_river_row | 1.019 |
| 上海外滩瑞吉酒店（原万达瑞华酒店） / [520214802](https://www.openstreetmap.org/way/520214802) | 2006.9 | stregis | 2.132 |
| OSM building 858807442 / [858807442](https://www.openstreetmap.org/way/858807442) | 2060.7 | provisional | — |
| OSM building 858807444 / [858807444](https://www.openstreetmap.org/way/858807444) | 2072.2 | provisional | — |
| 中国人保大厦 / [250067019](https://www.openstreetmap.org/way/250067019) | 2072.4 | picc | 2.582 |
| OSM building 694630326 / [694630326](https://www.openstreetmap.org/way/694630326) | 2125.7 | provisional | — |
| OSM building 408450698 / [408450698](https://www.openstreetmap.org/way/408450698) | 2126.0 | provisional | — |
| OSM building 702173485 / [702173485](https://www.openstreetmap.org/way/702173485) | 2136.0 | provisional | — |
| 古城公园丹凤楼一尺花园（OSM旧称高博金融家俱乐部） / [694630313](https://www.openstreetmap.org/way/694630313) | 2180.0 | one_step | 1.370 |
| OSM building 694630324 / [694630324](https://www.openstreetmap.org/way/694630324) | 2266.5 | provisional | — |
| OSM building 1287050296 / [1287050296](https://www.openstreetmap.org/way/1287050296) | 2384.3 | provisional | — |
| 沪南钱业公所（胡问遂艺术馆） / [389702055](https://www.openstreetmap.org/way/389702055) | 2431.3 | qianye | 5.297 |
| OSM building 1287050299 / [1287050299](https://www.openstreetmap.org/way/1287050299) | 2447.1 | provisional | — |
| 古城公园8号门公共厕所（人民路333号） / [694630319](https://www.openstreetmap.org/way/694630319) | 2451.8 | park_toilet | — |
| OSM building 389701990 / [389701990](https://www.openstreetmap.org/way/389701990) | 2478.7 | provisional | — |
| OSM building 389701816 / [389701816](https://www.openstreetmap.org/way/389701816) | 2488.1 | provisional | — |
| 人民路古城公园西侧圆顶旧楼 / [389701999](https://www.openstreetmap.org/way/389701999) | 2496.6 | park_corner | 3.812 |
| OSM building 1287050301 / [1287050301](https://www.openstreetmap.org/way/1287050301) | 2498.0 | provisional | — |
| 福佑商厦 / [389702034](https://www.openstreetmap.org/way/389702034) | 2531.1 | fuyou_market | 4.393 |
| 上海滩商厦 / [292818816](https://www.openstreetmap.org/way/292818816) | 2546.6 | shanghaitan | 5.501 |
| 外滩NEO / [389701925](https://www.openstreetmap.org/way/389701925) | 2585.1 | neo | 5.467 |
| 悦园商厦 / [83133885](https://www.openstreetmap.org/way/83133885) | 2599.6 | yueyuan | 15.761 |
| 紫锦城百货 / [389701905](https://www.openstreetmap.org/way/389701905) | 2633.9 | zijin | 16.123 |
| OSM building 389701946 / [389701946](https://www.openstreetmap.org/way/389701946) | 2655.4 | provisional | — |
| OSM building 389701974 / [389701974](https://www.openstreetmap.org/way/389701974) | 2669.2 | provisional | — |
| OSM building 297827879 / [297827879](https://www.openstreetmap.org/way/297827879) | 2709.8 | provisional | — |
| OSM building 1198559399 / [1198559399](https://www.openstreetmap.org/way/1198559399) | 2768.0 | provisional | — |
| 乐飞百货 / [389701893](https://www.openstreetmap.org/way/389701893) | 2768.7 | provisional | — |
| OSM building 446934325 / [446934325](https://www.openstreetmap.org/way/446934325) | 2786.0 | provisional | — |
| OSM building 389702014 / [389702014](https://www.openstreetmap.org/way/389702014) | 2793.8 | provisional | — |
| OSM building 446934334 / [446934334](https://www.openstreetmap.org/way/446934334) | 2798.2 | provisional | — |
| OSM building 389701879 / [389701879](https://www.openstreetmap.org/way/389701879) | 2802.5 | provisional | — |
| 豫园鄂尔多斯广场 / [389702099](https://www.openstreetmap.org/way/389702099) | 2836.9 | provisional | — |
| OSM building 378107226 / [378107226](https://www.openstreetmap.org/way/378107226) | 2850.2 | provisional | — |
| OSM building 1198554861 / [1198554861](https://www.openstreetmap.org/way/1198554861) | 2876.5 | provisional | — |
| OSM building 1198554862 / [1198554862](https://www.openstreetmap.org/way/1198554862) | 2876.8 | provisional | — |
| 人民路河南南路口全季酒店所在大楼 / [369238001](https://www.openstreetmap.org/way/369238001) | 2965.9 | ji_hotel | 10.502 |
| 河南南路人民路口西北侧沿街历史楼 / [378107242](https://www.openstreetmap.org/way/378107242) | 3000.8 | henan_heritage | 7.458 |
| 福佑门小商品市场 / [300480894](https://www.openstreetmap.org/way/300480894) | 3039.0 | fuyoumen | 4.500 |

其中41个scope way不含全季高层补充部件447021394。该部件与369238001同一模型，不另算独立建筑。16个照片专属builder对应16个scope way，额外覆盖该1个上部部件；25个provisional为明确未完成项。
