# 资产来源与许可 / Asset sources

本项目保持私有。以下记录用于来源追溯和个人开发，不代表重新授权。完整记录位于 references；原文件及派生哈希位于资源恢复清单。

## 当前运行车辆

| 车型 ID | 作者 | 许可 | 原作 | 运行文件 |
| --- | --- | --- | --- | --- |
| su7 | Mona x Supercars (Car2022) | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/xiaomi-su7-ca2cda599f5341068c992c9f44551bf9) | `public/vehicles/rigged/su7.glb` |
| model-3 | brandonleong28 | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/tesla-model-3-2024-36c52f3f89f6439c90310f14e8ff33f2) | `public/vehicles/rigged/model-3.glb` |
| dolphin | Nazh Design | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/2024-byd-dolphin-premium-long-range-8d30880667524cf3abb9e3e66c5299b5) | `public/vehicles/rigged/dolphin.glb` |
| model-y | Nieve5677 | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/tesla-model-y-bc8ac22c744b4d11b92f2f31ab0297d0) | `public/vehicles/rigged/model-y.glb` |
| yuan-up | Ddiaz Design | CC-BY-NC-SA-4.0 | [原作](https://sketchfab.com/3d-models/2024-byd-atto-2-2e04b67017ed49e982a1f0737eb7f0ae) | `public/vehicles/rigged/yuan-up.glb` |
| urus | Kai Xiang (https://sketchfab.com/kirikom9000) | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/lamborghini-urus-2018-32964087f5d24c3e90482724ddfc2fef) | `public/vehicles/rigged/urus.glb` |
| porsche-911 | SeKali / formerly fewdd (@zh.200.c) | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/68d8ef218d7e42adbd4425dc43629705) | `public/vehicles/rigged/porsche-911.glb` |
| alphard | Nieve5677 (@niev) | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/toyota-alphard-iii-2015-c3b0c9b6363945e0b27d020404198b0f) | `public/vehicles/rigged/alphard.glb` |
| g63 | Outlaw Games™ (https://sketchfab.com/Outlaw_Games) | CC-BY-NC-4.0 | [原作](https://sketchfab.com/3d-models/2020-mercedes-benz-g-class-amg-g63-52296f1a65d54a85a2ed7cb67604e554) | `public/vehicles/rigged/g63.glb` |
| ferrari-488 | Turbostuart (@Turbostuart) | CC-BY-4.0 | [原作](https://sketchfab.com/3d-models/ferrari-488-gtb-c2bca88f04044daaa7c0274a9c0f2cc1) | `public/vehicles/rigged/ferrari-488.glb` |

官方模型元数据在本轮逐项读取，见 `references/asset-license-checks-2026-09-10.json`。作者标注许可不等于独立核实所有组成部分的权属。元 UP、G63 含非商业限制；Alphard 保留第三方标记的来源疑点。私有保存不消除这些条件，也不授权未来公开附件或增加新的用途。

## 地图、照片与材质

- 地图／路线／建筑轮廓：© OpenStreetMap contributors，ODbL 1.0；见 [OSM](https://www.openstreetmap.org/copyright)、`references/tourism/map-source.json` 和 `loop-map-source.json`。
- 天空与部分路面材质：Poly Haven CC0；见 [许可](https://polyhaven.com/license)、`references/tourism/environment.json` 与 `street-textures.json`。
- 建筑照片：许可包括 CC0、CC BY、多版本 CC BY-SA，以及只能保留作参考的图片。原作、作者、许可、用途和来源文件逐条见[来源目录](ASSET_SOURCE_CATALOG.md)。
- 生成图与派生立面：见 `generated-streets.json`、`generated-facade-instructions.json` 和设计参考包。AI 处理、压缩或合并不自动清除源图许可。
- 完整 GLB、分块和 Blender 工程是多来源内容的集合，各组成部分保留自己的来源与条件。

## 代码与工具

Three.js、meshoptimizer、Draco、Vite、TypeScript 等按对应上游许可使用，具体依赖记录见 `private-backup/dependency-licenses.json`。本次未给项目添加整体 MIT 授权；此前未发布的公开候选位于本地 release/open-source，不属于当前私有仓库。

[第三方详细说明](../THIRD_PARTY_NOTICES.md)保存历史署名和修改方式；[同类项目参考](RELATED_PROJECTS.md)记录文档组织参考。
