import apiClient from './index'

export const settingsApi = {
  async getSettings() {
    const response = await apiClient.get('/v1/settings/')
    return response.data
  },

  async getSetting(id) {
    const response = await apiClient.get(`/v1/settings/${id}`)
    return response.data
  },

  async createSetting(data) {
    const response = await apiClient.post('/v1/settings', data)
    return response.data
  },

  async updateSetting(id, data) {
    const response = await apiClient.patch(`/v1/settings/${id}`, data)
    return response.data
  },

  async deleteSetting(id) {
    const response = await apiClient.delete(`/v1/settings/${id}`)
    return response.data
  },

  async updatePreferences(preferences) {
    const settings = await this.getSettings()
    const preferencesData = settings.data?.list || settings.data || []

    const promptConfigSetting = preferencesData.find(
      (s) => s.key === 'prompt_config'
    )

    const promises = []

    if (promptConfigSetting) {
      // Only keep allowed fields (language and scene)
      // This ensures deleted fields (like custom prompts) are actually removed
      // Preserve existing values if not provided in preferences
      const currentValue = promptConfigSetting.value || {}
      const updatedValue = {
        // Only update fields that are explicitly provided in preferences
        language: preferences.hasOwnProperty('language')
          ? preferences.language
          : currentValue.language,
        scene: preferences.hasOwnProperty('scene')
          ? preferences.scene
          : currentValue.scene
      }

      promises.push(
        this.updateSetting(promptConfigSetting.id, {
          value: updatedValue
        })
      )
    } else {
      const promptConfigValue = {}

      if (preferences.language) {
        promptConfigValue.language = preferences.language
      }

      if (preferences.scene) {
        promptConfigValue.scene = preferences.scene
      }

      if (Object.keys(promptConfigValue).length > 0) {
        promises.push(
          this.createSetting({
            key: 'prompt_config',
            value: promptConfigValue,
            description: 'User prompt configuration (language and scene)'
          })
        )
      }
    }

    await Promise.all(promises)
  },

  async getPreferences() {
    try {
      const settings = await this.getSettings()

      // Handle different response formats
      let settingsData = []
      if (Array.isArray(settings)) {
        settingsData = settings
      } else if (settings?.data) {
        if (Array.isArray(settings.data)) {
          settingsData = settings.data
        } else if (
          settings.data?.results &&
          Array.isArray(settings.data.results)
        ) {
          settingsData = settings.data.results
        } else if (settings.data?.list && Array.isArray(settings.data.list)) {
          settingsData = settings.data.list
        }
      }

      const promptConfigSetting = settingsData.find(
        (s) => s.key === 'prompt_config'
      )

      return {
        language: promptConfigSetting?.value?.language || null,
        scene: promptConfigSetting?.value?.scene || null
      }
    } catch (error) {
      // Return empty preferences if settings endpoint fails
      return {
        language: null,
        scene: null
      }
    }
  },

  async getEmailAliases() {
    const response = await apiClient.get('/v1/settings/email-aliases')
    return response.data
  },

  async createEmailAlias(alias) {
    const response = await apiClient.post('/v1/settings/email-aliases', {
      alias
    })
    return response.data
  },

  async deleteEmailAlias(id) {
    const response = await apiClient.delete(`/v1/settings/email-aliases/${id}`)
    return response.data
  },

  async validateAlias(alias) {
    const response = await apiClient.post(
      '/v1/settings/email-aliases/validate',
      { alias }
    )
    return response.data
  },

  async getGoogleNewsConfig() {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const googleNewsConfigSetting = settingsData.find(
      (s) => s.key === 'google_news_config'
    )

    // Return actual values from database (allow empty arrays)
    // filter_words is user-defined custom words, defaults to [] (not base filter words)
    return {
      filter_words: Array.isArray(googleNewsConfigSetting?.value?.filter_words)
        ? googleNewsConfigSetting.value.filter_words
        : [],
      has_words: Array.isArray(googleNewsConfigSetting?.value?.has_words)
        ? googleNewsConfigSetting.value.has_words
        : [],
      target_language:
        googleNewsConfigSetting?.value?.target_language || 'zh-CN',
      target_region: googleNewsConfigSetting?.value?.target_region || 'CN'
    }
  },

  async updateGoogleNewsConfig(config) {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const googleNewsConfigSetting = settingsData.find(
      (s) => s.key === 'google_news_config'
    )

    // Only keep allowed fields (filter_words, has_words, target_language, target_region)
    // This ensures deleted fields are actually removed and allows empty arrays
    const updatedValue = {
      filter_words: Array.isArray(config.filter_words)
        ? config.filter_words
        : [],
      has_words: Array.isArray(config.has_words) ? config.has_words : [],
      target_language: config.target_language || 'zh-CN',
      target_region: config.target_region || 'CN'
    }

    if (googleNewsConfigSetting) {
      return await this.updateSetting(googleNewsConfigSetting.id, {
        value: updatedValue
      })
    } else {
      return await this.createSetting({
        key: 'google_news_config',
        value: updatedValue,
        description: 'Google News collection configuration'
      })
    }
  },

  async getGithubConfig() {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const githubConfigSetting = settingsData.find(
      (s) => s.key === 'github_config'
    )

    return {
      github_token: githubConfigSetting?.value?.github_token || ''
    }
  },

  async updateGithubConfig(config) {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const githubConfigSetting = settingsData.find(
      (s) => s.key === 'github_config'
    )

    if (githubConfigSetting) {
      const currentValue = githubConfigSetting.value || {}
      // Only keep allowed fields (github_token and filter_words)
      // This ensures deleted fields (like prompts) are actually removed
      const updatedValue = {
        github_token: config.github_token || '',
        filter_words: currentValue.filter_words || []
      }

      return await this.updateSetting(githubConfigSetting.id, {
        value: updatedValue
      })
    } else {
      return await this.createSetting({
        key: 'github_config',
        value: {
          github_token: config.github_token || '',
          filter_words: []
        },
        description: 'GitHub collection configuration (token, etc.)'
      })
    }
  },

  async validateGithubConfig(config) {
    const response = await apiClient.post('/v1/settings/validate-github', {
      github_token: config.github_token || ''
    })
    return response.data
  },

  async getSocialOssConfig() {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const socialOssConfigSetting = settingsData.find(
      (s) => s.key === 'social_oss_config'
    )

    return {
      enable: socialOssConfigSetting?.value?.enable ?? false,
      access_key_id: socialOssConfigSetting?.value?.access_key_id || '',
      access_key_secret: socialOssConfigSetting?.value?.access_key_secret || '',
      bucket_name: socialOssConfigSetting?.value?.bucket_name || '',
      endpoint: socialOssConfigSetting?.value?.endpoint || '',
      region: socialOssConfigSetting?.value?.region || '',
      use_virtual_style:
        socialOssConfigSetting?.value?.use_virtual_style || false
    }
  },

  async updateSocialOssConfig(config) {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const socialOssConfigSetting = settingsData.find(
      (s) => s.key === 'social_oss_config'
    )

    if (socialOssConfigSetting) {
      const currentValue = socialOssConfigSetting.value || {}
      const updatedValue = {
        ...currentValue,
        enable: config.enable ?? false,
        access_key_id: config.access_key_id || '',
        access_key_secret: config.access_key_secret || '',
        bucket_name: config.bucket_name || '',
        endpoint: config.endpoint || '',
        region: config.region || '',
        use_virtual_style: config.use_virtual_style || false
      }

      return await this.updateSetting(socialOssConfigSetting.id, {
        value: updatedValue
      })
    } else {
      return await this.createSetting({
        key: 'social_oss_config',
        value: {
          enable: config.enable ?? false,
          access_key_id: config.access_key_id || '',
          access_key_secret: config.access_key_secret || '',
          bucket_name: config.bucket_name || '',
          endpoint: config.endpoint || '',
          region: config.region || '',
          use_virtual_style: config.use_virtual_style || false
        },
        description: 'Social media OSS configuration for article storage'
      })
    }
  },

  async validateSocialOssConfig(config) {
    try {
      const response = await apiClient.post(
        '/v1/settings/validate-social-oss',
        config
      )
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async getPublishOssConfig() {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const publishOssConfigSetting = settingsData.find(
      (s) => s.key === 'publish_oss_config'
    )

    return {
      use_same_as_storage:
        publishOssConfigSetting?.value?.use_same_as_storage ?? true,
      access_key_id: publishOssConfigSetting?.value?.access_key_id || '',
      access_key_secret:
        publishOssConfigSetting?.value?.access_key_secret || '',
      bucket_name: publishOssConfigSetting?.value?.bucket_name || '',
      endpoint: publishOssConfigSetting?.value?.endpoint || '',
      region: publishOssConfigSetting?.value?.region || '',
      use_virtual_style:
        publishOssConfigSetting?.value?.use_virtual_style || false
    }
  },

  async updatePublishOssConfig(config) {
    const settings = await this.getSettings()
    const settingsData = settings.data?.list || settings.data || []

    const publishOssConfigSetting = settingsData.find(
      (s) => s.key === 'publish_oss_config'
    )

    if (publishOssConfigSetting) {
      const currentValue = publishOssConfigSetting.value || {}
      const updatedValue = {
        ...currentValue,
        use_same_as_storage: config.use_same_as_storage ?? true,
        access_key_id: config.access_key_id || '',
        access_key_secret: config.access_key_secret || '',
        bucket_name: config.bucket_name || '',
        endpoint: config.endpoint || '',
        region: config.region || '',
        use_virtual_style: config.use_virtual_style || false
      }

      return await this.updateSetting(publishOssConfigSetting.id, {
        value: updatedValue
      })
    } else {
      return await this.createSetting({
        key: 'publish_oss_config',
        value: {
          use_same_as_storage: config.use_same_as_storage ?? true,
          access_key_id: config.access_key_id || '',
          access_key_secret: config.access_key_secret || '',
          bucket_name: config.bucket_name || '',
          endpoint: config.endpoint || '',
          region: config.region || '',
          use_virtual_style: config.use_virtual_style || false
        },
        description:
          'Object storage configuration for article publish monitoring'
      })
    }
  },

  async validatePublishOssConfig(config) {
    try {
      const response = await apiClient.post(
        '/v1/settings/validate-publish-oss',
        config
      )
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async getJiraConfig() {
    try {
      const response = await apiClient.get('/v1/config/key/jira_config/')
      return (
        response.data?.value || {
          enable: false,
          server_url: '',
          username: '',
          api_token: '',
          project_key: ''
        }
      )
    } catch (error) {
      if (error.response?.status === 404) {
        return {
          enable: false,
          server_url: '',
          username: '',
          api_token: '',
          project_key: ''
        }
      }
      throw error
    }
  },

  async updateJiraConfig(config) {
    try {
      const response = await apiClient.put('/v1/config/key/jira_config/', {
        value: {
          enable: config.enable ?? false,
          server_url: config.server_url || '',
          username: config.username || '',
          api_token: config.api_token || '',
          project_key: config.project_key || ''
        },
        value_type: 'object',
        category: 'jira',
        description: 'JIRA configuration'
      })
      return response.data
    } catch (error) {
      if (error.response?.status === 404) {
        const response = await apiClient.post('/v1/config/', {
          key: 'jira_config',
          value: {
            enable: config.enable ?? false,
            server_url: config.server_url || '',
            username: config.username || '',
            api_token: config.api_token || '',
            project_key: config.project_key || ''
          },
          value_type: 'object',
          category: 'jira',
          description: 'JIRA configuration'
        })
        return response.data
      }
      throw error
    }
  },

  async getGitLabConfig() {
    try {
      const response = await apiClient.get('/v1/config/key/gitlab_config/')
      return (
        response.data?.value || {
          enable: false,
          server_url: '',
          access_token: '',
          project_id: ''
        }
      )
    } catch (error) {
      if (error.response?.status === 404) {
        return {
          enable: false,
          server_url: '',
          access_token: '',
          project_id: ''
        }
      }
      throw error
    }
  },

  async updateGitLabConfig(config) {
    try {
      const response = await apiClient.put('/v1/config/key/gitlab_config/', {
        value: {
          enable: config.enable ?? false,
          server_url: config.server_url || '',
          access_token: config.access_token || '',
          project_id: config.project_id || ''
        },
        value_type: 'object',
        category: 'gitlab',
        description: 'GitLab configuration'
      })
      return response.data
    } catch (error) {
      if (error.response?.status === 404) {
        const response = await apiClient.post('/v1/config/', {
          key: 'gitlab_config',
          value: {
            enable: config.enable ?? false,
            server_url: config.server_url || '',
            access_token: config.access_token || '',
            project_id: config.project_id || ''
          },
          value_type: 'object',
          category: 'gitlab',
          description: 'GitLab configuration'
        })
        return response.data
      }
      throw error
    }
  },

  async getLLMConfig() {
    try {
      const response = await apiClient.get('/v1/config/key/llm_config/')
      return (
        response.data?.value || {
          provider: 'openai',
          openai: {
            api_key: '',
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4'
          },
          azure_openai: {
            api_key: '',
            endpoint: '',
            deployment_name: '',
            api_version: '2024-02-15-preview'
          }
        }
      )
    } catch (error) {
      if (error.response?.status === 404) {
        return {
          provider: 'openai',
          openai: {
            api_key: '',
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4'
          },
          azure_openai: {
            api_key: '',
            endpoint: '',
            deployment_name: '',
            api_version: '2024-02-15-preview'
          }
        }
      }
      throw error
    }
  },

  async updateLLMConfig(config) {
    try {
      const response = await apiClient.put('/v1/config/key/llm_config/', {
        value: {
          provider: config.provider || 'openai',
          openai: {
            api_key: config.openai?.api_key || '',
            base_url: config.openai?.base_url || 'https://api.openai.com/v1',
            model: config.openai?.model || 'gpt-4'
          },
          azure_openai: {
            api_key: config.azure_openai?.api_key || '',
            endpoint: config.azure_openai?.endpoint || '',
            deployment_name: config.azure_openai?.deployment_name || '',
            api_version:
              config.azure_openai?.api_version || '2024-02-15-preview'
          }
        },
        value_type: 'object',
        category: 'llm',
        description: 'LLM configuration (OpenAI, Azure OpenAI)'
      })
      return response.data
    } catch (error) {
      if (error.response?.status === 404) {
        const response = await apiClient.post('/v1/config/', {
          key: 'llm_config',
          value: {
            provider: config.provider || 'openai',
            openai: {
              api_key: config.openai?.api_key || '',
              base_url: config.openai?.base_url || 'https://api.openai.com/v1',
              model: config.openai?.model || 'gpt-4'
            },
            azure_openai: {
              api_key: config.azure_openai?.api_key || '',
              endpoint: config.azure_openai?.endpoint || '',
              deployment_name: config.azure_openai?.deployment_name || '',
              api_version:
                config.azure_openai?.api_version || '2024-02-15-preview'
            }
          },
          value_type: 'object',
          category: 'llm',
          description: 'LLM configuration (OpenAI, Azure OpenAI)'
        })
        return response.data
      }
      throw error
    }
  },

  async getFeishuConfig() {
    try {
      const response = await apiClient.get('/v1/config/key/feishu_config/')
      return (
        response.data?.value || {
          enable: false,
          app_id: '',
          app_secret: '',
          webhook_url: ''
        }
      )
    } catch (error) {
      if (error.response?.status === 404) {
        return {
          enable: false,
          app_id: '',
          app_secret: '',
          webhook_url: ''
        }
      }
      throw error
    }
  },

  async updateFeishuConfig(config) {
    try {
      const response = await apiClient.put('/v1/config/key/feishu_config/', {
        value: {
          enable: config.enable ?? false,
          app_id: config.app_id || '',
          app_secret: config.app_secret || '',
          webhook_url: config.webhook_url || ''
        },
        value_type: 'object',
        category: 'feishu',
        description: 'Feishu configuration'
      })
      return response.data
    } catch (error) {
      if (error.response?.status === 404) {
        const response = await apiClient.post('/v1/config/', {
          key: 'feishu_config',
          value: {
            enable: config.enable ?? false,
            app_id: config.app_id || '',
            app_secret: config.app_secret || '',
            webhook_url: config.webhook_url || ''
          },
          value_type: 'object',
          category: 'feishu',
          description: 'Feishu configuration'
        })
        return response.data
      }
      throw error
    }
  },

  async getSMTPConfig() {
    try {
      const response = await apiClient.get('/v1/config/key/smtp_config/')
      return (
        response.data?.value || {
          enable: false,
          host: '',
          port: 587,
          username: '',
          password: '',
          use_tls: true,
          use_ssl: false,
          from_email: '',
          from_name: ''
        }
      )
    } catch (error) {
      if (error.response?.status === 404) {
        return {
          enable: false,
          host: '',
          port: 587,
          username: '',
          password: '',
          use_tls: true,
          use_ssl: false,
          from_email: '',
          from_name: ''
        }
      }
      throw error
    }
  },

  async updateSMTPConfig(config) {
    try {
      const response = await apiClient.put('/v1/config/key/smtp_config/', {
        value: {
          enable: config.enable ?? false,
          host: config.host || '',
          port: config.port || 587,
          username: config.username || '',
          password: config.password || '',
          use_tls: config.use_tls ?? true,
          use_ssl: config.use_ssl ?? false,
          from_email: config.from_email || '',
          from_name: config.from_name || ''
        },
        value_type: 'object',
        category: 'smtp',
        description: 'SMTP email configuration'
      })
      return response.data
    } catch (error) {
      if (error.response?.status === 404) {
        const response = await apiClient.post('/v1/config/', {
          key: 'smtp_config',
          value: {
            enable: config.enable ?? false,
            host: config.host || '',
            port: config.port || 587,
            username: config.username || '',
            password: config.password || '',
            use_tls: config.use_tls ?? true,
            use_ssl: config.use_ssl ?? false,
            from_email: config.from_email || '',
            from_name: config.from_name || ''
          },
          value_type: 'object',
          category: 'smtp',
          description: 'SMTP email configuration'
        })
        return response.data
      }
      throw error
    }
  },

  async validateJiraConfig(config) {
    try {
      const response = await apiClient.post('/v1/config/validate/jira/', {
        ...config
      })
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async validateGitLabConfig(config) {
    try {
      const response = await apiClient.post('/v1/config/validate/gitlab/', {
        ...config
      })
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async validateLLMConfig(config) {
    try {
      const response = await apiClient.post('/v1/config/validate/llm/', {
        ...config
      })
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async validateFeishuConfig(config) {
    try {
      const response = await apiClient.post('/v1/config/validate/feishu/', {
        ...config
      })
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  },

  async validateSMTPConfig(config) {
    try {
      const response = await apiClient.post('/v1/config/validate/smtp/', {
        ...config
      })
      return response.data
    } catch (error) {
      if (error.response?.data) {
        return error.response.data
      }
      throw error
    }
  }
}
