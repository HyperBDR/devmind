# 云计费依赖与安装说明

## 腾讯云（Tencent Cloud）依赖

腾讯云 Provider 依赖以下 Python 包（已写入 `pyproject.toml`）：

- `tencentcloud-sdk-python-common`
- `tencentcloud-sdk-python-billing`

### Docker 环境

使用项目 Dockerfile 构建镜像时，会通过 **uv** 根据 `pyproject.toml` 安装全部依赖，**无需在宿主机上单独执行 pip**。腾讯云 SDK 会在镜像构建时自动安装。

### 宿主机上 pip 报错：`X509_V_FLAG_NOTIFY_POLICY`

若在宿主机执行 `pip install tencentcloud-sdk-python-common tencentcloud-sdk-python-billing` 时出现：

```text
AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'
```

这是**系统 Python 的 pip 与 pyOpenSSL/OpenSSL 不兼容**导致的（与腾讯云 SDK 本身无关）。可选用以下方式之一：

1. **用 Docker 运行项目（推荐）**  
   在容器内依赖由 pyproject.toml 统一安装，无需在宿主机用 pip 装腾讯云 SDK。

2. **用模块方式调用 pip**  
   ```bash
   python3 -m pip install tencentcloud-sdk-python-common tencentcloud-sdk-python-billing
   ```

3. **用 get-pip.py 重装/升级 pip**  
   ```bash
   curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
   python3 get-pip.py --force-reinstall
   ```
   然后再执行：  
   `pip install tencentcloud-sdk-python-common tencentcloud-sdk-python-billing`

4. **使用 uv 安装（若已安装 uv）**  
   ```bash
   uv pip install tencentcloud-sdk-python-common tencentcloud-sdk-python-billing
   ```

### 未安装腾讯云 SDK 时的行为

腾讯云 Provider 为**可选依赖**：若未安装上述 SDK，云计费应用仍可正常启动，仅 **tencentcloud** 类型不可用；其他云（如 AWS、华为、阿里云、Azure）不受影响。选择腾讯云时会提示不支持的 Provider。
