# 候选上游版本元数据追踪

本修订仅交付 `ci/p0-01d-metadata-tracking-v2`，未部署至默认分支，未执行真实 apply 或 schedule 测试。
不表示 P0-01D 验收通过，也不关闭 XN-001 / XN-009。

## 分支职责

- `master`：承载经审查的调度代码；不自动追赶上游产品提交。
- `upstream-tracking`：XN-owned metadata-only tracking branch，唯一自动写入目标。
  它只包含 `UPSTREAM_TRACKING.json`，不是官方源码镜像。首次提交无 parent；以后每次更新以旧 metadata
  commit 为唯一 parent，保持线性历史。commit tree 和所有 ancestors 均不得包含产品源码或 `.github/workflows`。
- `xn-main`：产品分支；整合候选版本须另建任务，经过审查及 CI。
- `custom-nav-controls`、`restore/*`、验证分支和 tags：自动化不写入。

## Plan / apply

手动运行默认 `plan`，仅读取 Git 对象、计算祖先关系并生成 JSON 与 job summary。
`apply` 允许首次创建 metadata root commit 或追加 metadata child commit。
JSON 已记录相同的官方 upstream SHA 时返回 `NO_CHANGE`，不创建 commit、不 push。
源、目标、ref 固定，调度代码只允许在 `2245676/rustdesk` 的 `refs/heads/master`，通过
`workflow_dispatch` 或 `schedule` 运行。其他分支不能运行写入 job，脚本还会独立拒绝错误上下文。

每次完整 fetch 官方 master 锁定一个 upstream SHA `U`，之后不再读取浮动 master。
验证 commit 类型、非 shallow 历史与 connectivity。若 tracking 存在，读取其 metadata commit `T`，
验证完整线性历史、每个 tree 仅含 regular `UPSTREAM_TRACKING.json`、严格 schema、固定来源/调度仓库及 ref，
并验证每条 JSON 的 `previous_upstream_sha` 对应上一条记录。畸形 JSON、重复字段、未知字段或隐藏的产品历史均拒绝。

旧记录的官方 SHA 为 `P`。只有 `P == U` 或 `P` 是官方 `U` 的祖先才接受；回退、分叉或 `P` 不在官方
master 完整历史中时返回 `UPSTREAM_DIVERGED`，不写入。
`FAST_FORWARD_CANDIDATE` 指官方 SHA 的逻辑推进，metadata branch 自身追加 child commit，不指向 `U`。

Git plumbing (`hash-object` / `mktree` / `commit-tree`) 只生成一个 JSON blob 的 tree，
bot identity 固定为 `XN Upstream Tracker <xn-upstream-tracker@users.noreply.github.com>`，不签名。
commit message 为 `chore(upstream): track <short upstream sha>`。创建时 `previous_upstream_sha = null`，
更新时为 `P`；JSON 还记录 schema version、官方 ref、调度仓库、workflow SHA、run id/attempt 和 event。

写入前重新读取 tracking；受信任的本地 pre-push hook 核对新 metadata commit SHA、唯一目标 ref 及服务器公告的旧 SHA，
普通 push 使用 Git 服务端旧 SHA 比较完成最后一道并发保护。首次创建也要求服务器公告该 ref 不存在。
不使用 force、lease、mirror、all、tags 或删除 refspec。只 push `NEW_METADATA_COMMIT:refs/heads/upstream-tracking`。
写入后读取真实 remote ref，再 fetch/验证该 metadata commit 的 tree、完整 JSON、`upstream_sha == U`
和 `previous_upstream_sha == P/null`；不符返回 `POST_PUSH_MISMATCH`。

上游只进入临时 bare 对象仓库，不 checkout，不运行上游 hooks、脚本、submodules 或 build。
临时 pre-push hook 只调用调度分支自身的可信校验代码。Git 忽略用户/系统配置、外部 hooks 与凭据助手。
token 只在写入目标 fork 时以进程环境中的 URL 限定 HTTP header 传入，不嵌入 URL、命令行或报告。
所有其他 heads/tags 的观察快照必须保持一致；外部并发修改也会使该检查失败，不会自动重试写入。

候选报告区分 metadata commit 和记录的官方 commit：`tracking_commit_before/after`、
`tracked_upstream_before/after`、锁定的 `upstream_sha`。Plan 中两组 before/after 都保持相同；apply 成功时
`tracked_upstream_after == upstream_sha`，`tracking_commit_after` 是另一个 metadata commit SHA。
报告还包含 workflow SHA、运行身份、观察到的 xn-main SHA、
候选动作、脱敏错误和 protected refs 比较结果。compare metadata 可用于后续审查；官方代码不镜像到 fork，
fork compare 页面的可用性须单独核验，官方 commit URL 仍指向真实来源。报告不代表产品已经整合或验证通过。
artifact 保留 7 天。GitHub Token 的 push 不被当作下游 CI 已启动的证据。

## 权限失败处理

plan job 仅 `contents: read`；apply job 仅 `contents: write`；其余权限为空。
使用默认 `GITHUB_TOKEN`，不依赖 `CUSTOM_REPO_TOKEN` 或 PAT。
旧 exact-commit 设计的真实 apply run `36746343185` 被 GitHub 拒绝，因为官方历史包含 workflow 变化，
默认 token 无 `workflows` 权限。本修订不复制官方 tree/history；它只把官方 SHA 写入无 workflow 文件的独立 metadata 历史。
不增加 `actions: write`、workflow scope、PAT 或 App private key。真实默认 token 对此新模型的写入能力仍须部署后单独实测。
若 GitHub 拒绝任何写入授权，返回非零并报告 `AUTH_CAPABILITY_BLOCKED`，
保留脱敏错误和相关 SHA；禁止改用 PAT、扩大权限或删除上游 workflow 文件绕过拒绝。
本次 `AUTH_CAPABILITY_LIVE = NOT_VERIFIED`；真实 token 写入能力须上线阶段实测。
只有生产 apply 实际写入且 remote ref/metadata 核验均成功后，报告才标 `WRITE_VERIFIED`。
本地测试和 `NO_CHANGE` 不提供新的写入权限验证。

后续产品整合必须读取 JSON 中的 `upstream_sha`，从 `https://github.com/rustdesk/rustdesk.git`
fetch 该 SHA 及完整历史，再按独立任务进行审查和 CI。不得把 metadata tracking branch 当成官方代码合并进 `xn-main`。

## 本地测试

Python 3.12+ 与 Git，无第三方 Python 依赖：

```sh
python3 -B -m unittest discover -s tests/xn -p test_sync_upstream.py -v
```

测试通过内部接口注入临时本地 bare 仓库，真实执行官方祖先核查、metadata plumbing 与 ref 更新，不写 GitHub。
核心回归在官方 `U` 引入 `.github/workflows/flutter-build.yml`，模拟目标服务拒绝传入的 workflow 历史；
metadata apply 必须成功，tracking tree/history 只含 JSON，目标产品 refs 不变，官方 `U` 对象不被传入 target。
生产 CLI 不接受 remote/ref 参数；缺失 mode 默认为 plan，非法参数不会变成 apply。

## 上线与回滚门禁

上线仍须依次完成：Main AI 验收 C3 CI、独立安全审查、单独授权部署到 master、
真实 workflow_dispatch 验证、真实 schedule 验证、tracking 与受保护 refs 核查，最后启用每日调度。
每日 cron 为 `17 3 * * *`，使用 UTC（日本时间 12:17）。
schedule 只从默认分支运行；当前交付分支上的 schedule 不表示已经部署。

后续激活验收可另行授权临时五分钟 schedule，再恢复每日 cron；本次不启用、不提交到 master。
GitHub 定时触发可能延迟，不能承诺五分钟内运行；未观察到真实 schedule 时记为 PENDING。

回滚仅停止或撤回调度 workflow，不重写 tracking 或产品历史，不使用 force/reset 回退仓库。
