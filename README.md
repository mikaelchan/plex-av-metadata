# plex-jav-metadata

JAV 元数据刮削 HTTP 服务 — Plex Metadata Agent

基于 JavSP 引擎，多源并发刮削，Docker 一键部署。

---

## 快速开始

```bash
git clone https://github.com/mikaelchan/plex-jav-metadata.git
cd plex-jav-metadata
docker compose up -d
```

## API

| 端点 | 用途 |
|------|------|
| `GET /` | Provider 声明（Plex 发现用，返回 XML） |
| `GET /metadata/{番号}` | 返回 Plex 格式元数据 |
| `POST /match` | Plex 搜索匹配（JSON body） |
| `GET /scrape/{番号}` | 手动刮削，返回 JSON |
| `GET /scrape/{番号}/nfo` | 下载 nfo 文件 |
| `GET /scrape/{番号}/cover` | 下载封面 |

## 注册到 Plex

1. 确保服务已启动
2. 打开 Plex Web 后台 → **设置 → 管理 → Metadata Agents**
3. 在 Metadata Agents 页面添加 provider URL：`http://192.168.50.5:8800`
4. Plex 会自动调用 `GET /` 发现 provider 能力
5. 注册成功后，在影片库的代理选项中会出现 **"JAV Metadata"**

![待补充截图]

## 测试刮削

```bash
curl http://localhost:8800/scrape/ABW-005
curl http://localhost:8800/scrape/ABW-005/nfo -o ABW-005.nfo
curl http://localhost:8800/scrape/ABW-005/cover -o poster.jpg
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `/data` | 临时数据目录 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 项目结构

```
plex-jav-metadata/
├── api/                # FastAPI 服务
│   ├── __main__.py    # 主入口 + 路由
│   └── scraper.py     # 刮削引擎（JavSP + 内置 fallback）
├── javsp/              # JavSP 刮削引擎
├── Dockerfile
├── docker-compose.yml
└── README.md
```
