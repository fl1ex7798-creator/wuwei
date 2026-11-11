# Spring Boot Security Hello World

Spring Boot **3.2.0** + Spring Security，提供用户名密码登录和需要认证的 Hello World API。

## 环境与启动

需要 JDK 17 或更高版本、Maven 3.6.3 或更高版本。

```bash
cd springboot-security-hello
mvn spring-boot:run
```

默认地址：`http://localhost:8080`。演示账号：`test`，密码：`123456`。密码通过 BCrypt 编码后存储在内存中。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/csrf` | 获取 CSRF Token，同时建立 Session |
| POST | `/api/login` | 表单参数 `username` 和 `password`；成功返回 JSON 和 Session Cookie |
| GET | `/api/hello` | 需要登录；返回纯文本 `Hello World`，未登录返回 401 |
| POST | `/api/logout` | 携带 CSRF Token 注销 Session，成功返回 204 |

登录请求使用 `application/x-www-form-urlencoded`，不是 JSON。登录失败返回 401；缺少或错误的 CSRF Token 返回 403。

## 使用 curl 验证

以下命令使用 Bash、curl 和 Python 3。所有命令在同一个终端中执行：

```bash
# 1. 未登录访问，预期 HTTP 401
curl -i http://localhost:8080/api/hello

# 2. 获取 CSRF Token，并保存 Cookie
csrf=$(curl -fsS -c cookies.txt http://localhost:8080/api/csrf \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

# 3. 登录，预期 HTTP 200 和 {"message":"Login successful","username":"test"}
curl -i -b cookies.txt -c cookies.txt \
  -H "X-CSRF-TOKEN: $csrf" \
  --data-urlencode 'username=test' \
  --data-urlencode 'password=123456' \
  http://localhost:8080/api/login

# 4. 携带登录 Cookie，预期 HTTP 200，响应体为 Hello World
curl -i -b cookies.txt http://localhost:8080/api/hello

# 5. 登录成功后 CSRF Token 会轮换，注销前重新获取
csrf=$(curl -fsS -b cookies.txt -c cookies.txt http://localhost:8080/api/csrf \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -i -X POST -b cookies.txt -c cookies.txt \
  -H "X-CSRF-TOKEN: $csrf" http://localhost:8080/api/logout

# 6. 注销后再次访问，预期 HTTP 401
curl -i -b cookies.txt http://localhost:8080/api/hello
```

## 测试与打包

```bash
mvn test
mvn clean package
java -jar target/springboot-security-hello-1.0.0.jar
```

集成测试验证未登录访问被拒绝、正确密码登录并访问 Hello World、注销、错误密码，以及 CSRF 防护。

此项目使用单机内存 Session 和固定演示账号，应用重启后登录状态失效。
