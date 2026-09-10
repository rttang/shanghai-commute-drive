# 来源与许可

## 地图

© OpenStreetMap contributors。原始地图数据库及派生数据按 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) 使用；[署名与版权说明](https://www.openstreetmap.org/copyright)。查询记录与快照在 `references/tourism/`，派生运行数据为 `public/tour-city.json`，转换程序为 `scripts/prepare_tourism_map.py`。游戏地图持续显示署名。本项目简化高程、车道、建筑内院与缺省高度，不是现实导航。

## 当前详细车辆

均通过用户已登录的 Sketchfab 下载入口获取，作者页面声明 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原包、下载记录和SHA-256在 `assets/vehicles/source/`。

| 资产 | 作者与原作 | 本项目修改 |
| --- | --- | --- |
| 小米SU7，2024款 | [Mona x Supercars / Car2022](https://sketchfab.com/3d-models/xiaomi-su7-ca2cda599f5341068c992c9f44551bf9) | 统一尺寸方向、去除内部与隐藏面、外观材质整理、网格和贴图压缩 |
| Tesla Model 3，2024 Highland | [brandonleong28](https://sketchfab.com/3d-models/tesla-model-3-2024-36c52f3f89f6439c90310f14e8ff33f2) | 统一方向尺寸、外观保留、隐藏面处理、玻璃与车漆、压缩 |
| BYD Dolphin，2024 Premium Long Range | [Nazh Design](https://sketchfab.com/3d-models/2024-byd-dolphin-premium-long-range-8d30880667524cf3abb9e3e66c5299b5) | 顶点色保留、法线和平滑修复、PBR材质分类、隐藏面与压缩 |

运行映射及页面署名在 `src/tour/vehicle-assets.json`。CC BY不表示汽车厂商背书。SU7旧镜像包只作历史来源记录，当前运行资产使用作者作品页官方转换包；AI星愿候选因几何质量不合格留在review目录，Model Y候选有第三方分发标记而未采用。其余七款仍是本项目生成的原型，不能当作已通过高保真验收的对应实车。

## 环境与街景

[Poly Haven](https://polyhaven.com/license)素材为CC0，当前使用：

- [Kloppenheim 05 Pure Sky](https://polyhaven.com/a/kloppenheim_05_puresky)：Greg Zaal、Jarod Guest，自然天空HDR；不是上海实拍HDR。
- [Asphalt 02](https://polyhaven.com/a/asphalt_02)：Rob Tuytel，沥青材质。
- [Stone Tile Wall](https://polyhaven.com/a/stone_tile_wall)：Charlotte Baglioni，石材色彩、法线和粗糙度。
- [Large Grey Tiles](https://polyhaven.com/a/large_grey_tiles)：Rob Tuytel，人行道材质。
- [Aerial Grass Rock](https://polyhaven.com/a/aerial_grass_rock)：Rob Tuytel，用于普通绿地的地表变化，不是上海公园实拍。
- [Bark Brown 01](https://polyhaven.com/a/bark_brown_01)：Rob Tuytel，保留为未采用的材质研究源图，不加载到当前页面。

精确下载URL、路径与哈希在 `references/tourism/environment.json` 和 `street-textures.json`。运行时只加载本地文件。

远处普通建筑使用共享材质；近处的十六栋立面建筑和东方明珠采用各自实拍参考。`assets/streets/references/` 保存源照片；`references/tourism/architecture-photos.json` 保存作者、拍摄日期、下载URL和SHA-256。以下照片不是实时街景，尤其正大广场参考拍摄于2009年；不能据此声称还原了2026年的全部招牌与店铺。

| 参考照片 | 摄影作者 | 许可 |
| --- | --- | --- |
| [Chartered Bank Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Chartered_Bank_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [North China Daily News Building 20250501.jpg](https://commons.wikimedia.org/wiki/File:North_China_Daily_News_Building_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Russo-Chinese Bank Building, Shanghai.JPG](https://commons.wikimedia.org/wiki/File:Russo-Chinese_Bank_Building,_Shanghai.JPG) | Livelikerw | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| [Customs House, Shanghai 20250501-1.jpg](https://commons.wikimedia.org/wiki/File:Customs_House,_Shanghai_20250501-1.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [HSBC Building, Shanghai 20250501-1.jpg](https://commons.wikimedia.org/wiki/File:HSBC_Building,_Shanghai_20250501-1.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Bank of China Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Bank_of_China_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Base of Oriental Pearl Tower.jpg](https://commons.wikimedia.org/wiki/File:Base_of_Oriental_Pearl_Tower.jpg) | Tim Sheerman-Chase | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) |
| [Sassoon House 20250501.jpg](https://commons.wikimedia.org/wiki/File:Sassoon_House_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Shanghai Palace Hotel 20250501.jpg](https://commons.wikimedia.org/wiki/File:Shanghai_Palace_Hotel_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Customs House, Shanghai 20250501-2.jpg](https://commons.wikimedia.org/wiki/File:Customs_House,_Shanghai_20250501-2.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Asia Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Asia_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Bank of Taiwan Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Bank_of_Taiwan_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Bank of Communications Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Bank_of_Communications_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [China Merchants Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:China_Merchants_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [正大广场白天外景.jpg](https://commons.wikimedia.org/wiki/File:%E6%AD%A3%E5%A4%A7%E5%B9%BF%E5%9C%BA%E7%99%BD%E5%A4%A9%E5%A4%96%E6%99%AF.jpg) | Hanahu55 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |

| [Shanghai Ocean Aquarium.jpg](https://commons.wikimedia.org/wiki/File:Shanghai_Ocean_Aquarium.jpg) | © Peter Potrowl | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0) |
| [Hang Seng Bank Tower.jpg](https://commons.wikimedia.org/wiki/File:Hang_Seng_Bank_Tower.jpg) | Baycrest | [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5) |
| [BEA Finance Tower.jpg](https://commons.wikimedia.org/wiki/File:BEA_Finance_Tower.jpg) | Baycrest | [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5) |

修改方式：内置 image_gen 参考原照片去除遮挡、校正透视、补全立面；Blender将结果映射到窗洞、线脚、柱廊、屋顶和有厚度的建筑主体，再转为JPEG并压缩几何。生成步骤可能补出照片未确认的细节，未见侧面属于推测。东方明珠使用照片观察结构与材质，不把整张照片贴在塔上。原始提示与生成图哈希在 `.dream-loop/photo-prompts.json`。

俄华道胜银行的派生立面PNG、运行JPEG及 `public/streets/photo-models/russo-chinese-bank.glb` 沿用 **CC BY-SA 3.0**；正大广场的对应派生资产沿用 **CC BY-SA 4.0**；恒生银行和东亚银行的对应派生资产沿用 **CC BY-SA 2.5**，海洋水族馆按 **CC BY 3.0** 署名使用。请随这些文件保留作者、源链接、许可链接和修改说明；未暗示摄影者、商标持有人或建筑业主背书。其余CC0参考不设署名限制，项目仍保留原作者记录。可编辑Blend是含不同许可资产的集合，各资产的来源和条件仍分别保留。内景候选 `super-brand-mall.jpg` 已明确标作 rejected-interior，未用于生成或运行建模。平安大楼候选因位于浦西而标作 rejected-location，未套用到浦东同名建筑。

目标街景图、远处通用历史立面、悬铃木叶片与树皮由内置 image_gen 生成，记录在 `generated-streets.json` 与 `.dream-loop/prompts.md`。懂车帝截图只作车辆外观观察，未作为游戏贴图。街景入口为 `scripts/build-streets.sh`，同时执行通用设施和实拍建筑两条独立生成程序。

## 开源方法与依赖

| 项目 | 版本/来源 | 使用方式 |
| --- | --- | --- |
| [javascript-racer](https://github.com/jakesgordon/javascript-racer/tree/3e8a060b5900755db27f899612a74a77427c853e) | `3e8a060b5900755db27f899612a74a77427c853e` | 参考道路与绘制组织；未导入音乐或精灵 |
| [threejs_car_demo](https://github.com/cconsta1/threejs_car_demo/tree/b6b143e898df406f83019c1d0156e4be1bfcfab8) | `b6b143e898df406f83019c1d0156e4be1bfcfab8` | 参考Three.js模块分层；未复制汽车资产 |
| [Dream Loop](https://github.com/achimala/dream-loop) | 2026-09-08查阅，MIT | 采用目标图—实现—截图比较的工作流程，未安装或复制其源码到产品 |

Three.js为MIT。Google Draco为Apache 2.0，运行解码器许可证位于 `public/decoders/draco/LICENSE`。Vite、TypeScript等保留包内许可。地图许可不覆盖其他来源资产，项目整体尚未指定开源许可证。项目未保存网站账号、Cookie或身份信息。

## 2026-09-09 轮轴与纹理派生变更

`public/vehicles/rigged/` 的SU7、Model 3和海豚GLB由上述对应作者的正式源包派生，继续使用各自CC BY 4.0署名。新增修改：移除内饰、保留转向时露出的轮胎外部几何、将原始连通车轮/轮毂拆分为独立轮轴、整理材质及编码精度；不是重新创作的车型版权，也不表示品牌背书。`rigged/prototypes/` 为项目已有程序化原型的轮轴派生版本。旧源包、原始GLB、预览和许可记录保留。

17个实拍建筑此次仅提高运行JPEG与几何编码精度，保留PNG原始尺寸与现有模型几何；原摄影者与派生资产的CC BY/CC BY-SA条件保持不变。

## 2026-09-09 完整街景新增照片与派生模型

本轮新增37张参考照片，34张用于外观参考、3张因室内、施工期或反射重复而排除但完整保留。逐照片原文件、日期、观察范围及SHA见 `references/tourism/streets-expansion-photos.json`。

| 照片 | 作者 | 许可 |
| --- | --- | --- |
| [Astor House Hotel (Shanghai) 20250501-1.jpg](https://commons.wikimedia.org/wiki/File:Astor_House_Hotel_(Shanghai)_20250501-1.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Jardine Matheson Building Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Jardine_Matheson_Building_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Great Northern Telegraph Building 20250501.jpg](https://commons.wikimedia.org/wiki/File:Great_Northern_Telegraph_Building_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Nissin Building 20250501.jpg](https://commons.wikimedia.org/wiki/File:Nissin_Building_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Former Yokohama Specie Bank Building Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Former_Yokohama_Specie_Bank_Building_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Yangtze Insurance Building 20250501.jpg](https://commons.wikimedia.org/wiki/File:Yangtze_Insurance_Building_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Union Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Union_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Banque de l'Indochine Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Banque_de_l%27Indochine_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [The Bund 20250501.jpg](https://commons.wikimedia.org/wiki/File:The_Bund_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Waibaidu Bridge 20250501-1.jpg](https://commons.wikimedia.org/wiki/File:Waibaidu_Bridge_20250501-1.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Waibaidu Bridge 20250501-2.jpg](https://commons.wikimedia.org/wiki/File:Waibaidu_Bridge_20250501-2.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Former Russo-Chinese Bank Building, Shanghai 20250501.jpg](https://commons.wikimedia.org/wiki/File:Former_Russo-Chinese_Bank_Building,_Shanghai_20250501.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [HSBC Building, Shanghai 20250501-2.jpg](https://commons.wikimedia.org/wiki/File:HSBC_Building,_Shanghai_20250501-2.jpg) | Suicasmo | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [2014.11.16.165410 Lujiazui Intersection Shanghai.jpg](https://commons.wikimedia.org/wiki/File:2014.11.16.165410_Lujiazui_Intersection_Shanghai.jpg) | Hermann Luyken | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Broadway Mansions Shanghai (2024) - img 01.jpg](https://commons.wikimedia.org/wiki/File:Broadway_Mansions_Shanghai_(2024)_-_img_01.jpg) | Chainwit. | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) |
| [Broadway Mansions Shanghai (2024) - img 04.jpg](https://commons.wikimedia.org/wiki/File:Broadway_Mansions_Shanghai_(2024)_-_img_04.jpg) | Chainwit. | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) |
| [Glen Line Building, Shanghai.jpg](https://commons.wikimedia.org/wiki/File:Glen_Line_Building,_Shanghai.jpg) | 钉钉 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [Shanghai Club Dec 2017.jpg](https://commons.wikimedia.org/wiki/File:Shanghai_Club_Dec_2017.jpg) | ScareCriterion12 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [Gutzlaff Signal Tower.jpg](https://commons.wikimedia.org/wiki/File:Gutzlaff_Signal_Tower.jpg) | 钉钉 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [Gutzlaff Signal Tower & The Bund.jpg](https://commons.wikimedia.org/wiki/File:Gutzlaff_Signal_Tower_%26_The_Bund.jpg) | 钉钉 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [有利大楼正门.jpg](https://commons.wikimedia.org/wiki/File:%E6%9C%89%E5%88%A9%E5%A4%A7%E6%A5%BC%E6%AD%A3%E9%97%A8.jpg) | Legolas1024 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| [有利大楼塔楼.jpg](https://commons.wikimedia.org/wiki/File:%E6%9C%89%E5%88%A9%E5%A4%A7%E6%A5%BC%E5%A1%94%E6%A5%BC.jpg) | Legolas1024 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| [Shanghai Tower bottom view (October 1st 2022).jpg](https://commons.wikimedia.org/wiki/File:Shanghai_Tower_bottom_view_(October_1st_2022).jpg) | Bechology | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) |
| [Shanghai Tower, August 2023.jpg](https://commons.wikimedia.org/wiki/File:Shanghai_Tower,_August_2023.jpg) | Francisco Javier PB | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [20191114 Jin Mao Tower-1.jpg](https://commons.wikimedia.org/wiki/File:20191114_Jin_Mao_Tower-1.jpg) | Balon Greyjoy | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| [Jin Mao Tower Close-Up.jpg](https://commons.wikimedia.org/wiki/File:Jin_Mao_Tower_Close-Up.jpg) | Jakob Montrasio | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) |
| [Shanghai World Financial Center (March 9th 2024).jpg](https://commons.wikimedia.org/wiki/File:Shanghai_World_Financial_Center_(March_9th_2024).jpg) | Bechology | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) |
| [Shanghai World Financial Center from basement.JPG](https://commons.wikimedia.org/wiki/File:Shanghai_World_Financial_Center_from_basement.JPG) | Popolon | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| [Shanghai IFC and Apple Store Pudong 20251126.jpg](https://commons.wikimedia.org/wiki/File:Shanghai_IFC_and_Apple_Store_Pudong_20251126.jpg) | This Photo was taken by Supanut Arunoprayote.

Feel free to use any of my images, but please mention me as the author and may send me a message.  (สามารถใช้ภาพได้อิสระ แต่กรุณาใส่เครดิตผู้ถ่ายและอาจส่งข้อความบอกกล่าวด้วย) 



Please do not upload an updated image here without consultation with the Author. The author would like to make corrections only at his own source. This ensures that the changes are preserved.Please if you think that any changes should be required, please inform the author.Otherwise you can upload a new image with a new name. Please use one of the templates derivative or extract. | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) |
| [Century Avenue, Pudong New Area, Shanghai.jpg](https://commons.wikimedia.org/wiki/File:Century_Avenue,_Pudong_New_Area,_Shanghai.jpg) | Federico | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| [Citigroup - panoramio.jpg](https://commons.wikimedia.org/wiki/File:Citigroup_-_panoramio.jpg) | zhanyoun | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| [Pudong Oriental Pearl Tower (18657707648).jpg](https://commons.wikimedia.org/wiki/File:Pudong_Oriental_Pearl_Tower_(18657707648).jpg) | shutterstuman | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) |
| [Standard Chartered Bank Tower.jpg](https://commons.wikimedia.org/wiki/File:Standard_Chartered_Bank_Tower.jpg) | Baycrest | [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5) |
| [Minor skyscrapers in Lujiazui, Shanghai as seen from Lujiazui Pedestrian Bridge 20120602 1.jpg](https://commons.wikimedia.org/wiki/File:Minor_skyscrapers_in_Lujiazui,_Shanghai_as_seen_from_Lujiazui_Pedestrian_Bridge_20120602_1.jpg) | DXR | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |

本轮校正立面由内置 image_gen 生成，源图、生成原件和移动硬盘副本均保留；提示集合位于 `references/tourism/generated-facade-instructions.json`，保存记录位于 `docs/evidence/tourism/street-master-generated-images.json`。独立窗洞、柱廊、屋顶、细部分体和摄影纹理一并纳入总模型。无照片的侧面、遮挡补全、部分层高与细节明确为推断。总GLB、分块及完整Blender工程为多个许可资产的集合，各组件继续遵守所列CC BY与CC BY-SA条款，包含上一轮俄华道胜、正大广场、恒生、东亚及水族馆的派生许可。地图沿用OpenStreetMap ODbL，不表示摄影者或建筑业主背书。

## meshoptimizer 1.1.1

[meshoptimizer](https://github.com/zeux/meshoptimizer) - MIT

```text
MIT License

Copyright (c) 2016-2026 Arseny Kapoulkine

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
