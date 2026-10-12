# 用户身份只读任务授权测试

测试应用已由用户发布 User token scope `task:task:read`。先验证用户身份能否读取原生自动化创建的指定虚构任务，不申请写权限、不修改任务或客户记录。

## 操作与实现边界

1. 测试应用安全设置增加重定向 URL `http://localhost:8765/callback`。官方文档的本地开发示例支持 localhost HTTP 回调；它只用于本机测试，不是生产云端地址。
2. 本机更新 crm_sync/oauth.py、tools/check_feishu_task_access.py、tools/check_feishu_user_task.py。
3. 用户运行 `python3.13 -B tools/check_feishu_user_task.py`，输入指定虚构客户名及隐藏的测试 App Secret；程序从已有本机配置读取测试标识，不要求重复输入。
4. 程序绑定 127.0.0.1:8765，生成随机 state 与 S256 PKCE，打开飞书官方授权页。用户确认测试应用、当前身份与只读 scope。不要发送授权回调地址栏或截图到聊天。
5. 授权码仅在内存换取用户访问令牌；测试表仍用租户身份核验，只有指定已关联任务的 GET 使用用户身份。不列取个人任务、不将用户令牌用于任意接口、不输出凭证。
6. 输出成功/身份匹配状态或脱敏错误。进程结束后不保存访问令牌、刷新令牌或 App Secret。拒绝、超时、错误state、重复参数及错误路径均停止。

## 官方来源与端点选择

- [获取授权码](https://open.feishu.cn/document/common-capabilities/sso/api/obtain-oauth-code)：登记回调 URL、state及PKCE S256；文档当前明确支持此授权页配合v2令牌接口。
- [获取用户令牌](https://open.feishu.cn/document/authentication-management/access-token/get-user-access-token)：JSON交换参数、localhost开发示例及新版迁移提示。

这次隔离验证使用文档明确描述的v1授权页面 + v2令牌交换 + 正确匹配PKCE。v2被标记为历史版本，不能将本探针当作完成生产OAuth架构。云端长期部署前应核实并迁移当前推荐端点，增加加密令牌存储、offline_access授权、刷新令牌轮换/并发控制及重新授权处理；尚未部署或实现这些生产能力。

## 验证结果

9 项模拟测试通过：标准PKCE向量、授权链接不含secret/verifier、合法回调、错误/缺失state、重复参数、错误路径、拒绝授权、缺失/过长授权码，以及租户表读取与用户任务读取分离。模拟结果不等于实际飞书用户授权成功，后续用户Mac与测试任务验收待执行。

没有修改应用设置、部署收费服务、调用真实客户记录或回写任何任务。回调页面禁止缓存，未记录请求路径，服务器仅监听本机地址。首次登录、浏览器和本机证书失败仍需按实际输出诊断。
