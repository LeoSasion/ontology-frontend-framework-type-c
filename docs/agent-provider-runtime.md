# Agent Provider 运行边界

## 角色

DeepSeek 是可选解释层，不是 BI 执行器、证据裁判或工具代理。每次请求按固定顺序处理：

1. 本地确定性运行时解析字段、关系、查询和 Receipt。
2. AIBI-C 构建有界、脱敏、证据优先的 Context。
3. Provider 可以解释已计算结果或提出一次必要澄清。
4. 本地答案始终权威；超时、限流、无密钥或无效响应直接降级。

Provider 不能执行任意 SQL、读取文件、修改数据、确认草案、删除对象或声称写入已完成。

## 出站数据

显式启用后，AIBI-C 只可能发送：当前问题、本地答案摘要和有界指标值、显示名称、已选择字段/聚合/筛选/关系描述、知识规则标识、证据状态和是否仍需确认。

以下内容不得出站：源文件和原始行、编译 SQL、动作 payload、数据库、API key、凭据引用、绝对路径、其他 AIBI 仓库标识和模型私有推理。Context 以 `aibi-agent-provider-context/v1` 规范化，并在发送前脱敏和预算裁剪。

不能离开工作站的数据必须使用 `AIBI_AGENT_PROVIDER=deterministic`。

## 配置

配置项及当前默认值以根目录 `.env.example` 为准：

```dotenv
AIBI_AGENT_PROVIDER=deterministic
DEEPSEEK_API_KEY=
DEEPSEEK_API_KEY_FILE=
DEEPSEEK_MODEL=
DEEPSEEK_TIMEOUT_MS=20000
DEEPSEEK_MAX_TOKENS=600
```

| 模式 | 行为 |
| --- | --- |
| `deterministic` | 从不调用外部 Provider，部署模板默认值 |
| `deepseek` | 有服务端密钥时调用，否则本地降级 |
| `auto` | 为本地兼容保留；不建议用于需要显式出站控制的部署 |

密钥只由本地 Node 服务读取，不进入 API 响应、Job、事件、Context、日志或回执。可用 `DEEPSEEK_API_KEY_FILE` 避免把密钥写入 `.env`。

## 失败与预算

- 结构错误、空响应和瞬态故障最多重试一次。
- Provider 生成的数字必须存在于本地证据上下文；越界数字和已完成写入声明会被拒绝。
- Context Budget 先移除可选诊断，保留决策、口径、阻塞和 Receipt；必需上下文本身超限时跳过 Provider。
- 审计只保存脱敏状态、耗时和降级原因，不保存密钥或响应错误正文。

## 验证

```powershell
npm run verify:provider
npm run verify:provider-live
```

普通回归只运行确定性 mock，不消耗模型额度。`verify:provider-live` 会发起有界真实请求，只在配置或网络路径变化时显式运行。

## 不在当前范围

当前不提供模型自主工具循环。未来任何工具调用仍必须经过现有 Capability、白名单查询、Workflow Stage 和显式确认边界。
