# DevMind Design Principles

This document states the core design principles that the DevMind project follows. All applications (Django apps and agentcore modules) should align with these principles.

---

## 1. Application self-management (decoupling)

**Principle:** For decoupling, each application (app) must **manage its own resources**. This includes but is not limited to:

- **Data / database**  
  Each app owns its models, migrations, and data. It does not depend on other apps’ tables for its core behaviour, nor does it expose its internal storage for other apps to query directly. Cross-app data needs are met via stable APIs or events, not shared tables.

- **APIs**  
  Each app defines and exposes its own HTTP (or other) interfaces. Callers use these interfaces rather than importing the app’s models or internal modules. Configuration that affects the app’s behaviour is either owned by the app (e.g. its own config table or settings namespace) or passed explicitly at call time (e.g. channel config by UUID).

- **Configuration**  
  App-specific configuration (feature flags, endpoints, channel selection, etc.) is managed within the app or via explicit contracts (e.g. call parameters, env/settings keys owned by the app). There is no global “app_config” or shared config store that other apps are required to use; each app can choose how it is configured.

**Implications:**

- Prefer **explicit call-time configuration** (e.g. passing `channel_config` or `channel_uuid`) over reading from a shared config store or another app’s database.
- New features that need “which channel / which endpoint” should be satisfied by the app’s own APIs or by parameters at the call boundary, not by coupling to a central config app.
- When removing or replacing a shared component (e.g. a global config app), no app should break if it already follows this principle (own data, own APIs, explicit config).

This principle is mandatory for keeping the system decoupled and for making apps replaceable and testable in isolation.

---

## 2. Application-side configuration when using shared modules (example)

Using the **cloud billing** module’s use of the shared notifier as an example:

- **Send target**  
  If the application needs to specify where to send notifications (e.g. which notification channel), the **application side** must add **explicit configuration** and a **configuration UI**, so that users or admins can choose within the app (e.g. select a configured channel by UUID). If the application does not configure a send target, then **no notification is sent** by design; the app does not rely on a default from the shared module or a global setting.

- **Level and granularity**  
  Alert level, whether to send, and how to scope behaviour (e.g. per cloud platform, per account) are all decided by the **application side**. For example, in cloud billing management, send behaviour can be tied to each cloud provider or each alert rule, rather than the shared notifier assuming a single global policy.

The shared module only provides the capability to “send using the given channel config”; whether to send, to whom, and at what level are all managed by the consuming app through its own configuration and UI.
