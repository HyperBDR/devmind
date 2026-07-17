/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { Product, Service, DiscountOption, Quotation } from './types';

export const MOCK_CATALOG_VERSION = 'onepro-template-may-2026-v1';

export const MOCK_PRODUCTS: Product[] = [
  {
    id: 'tpl-product-2-hypermotion-license-with-a-validity-per',
    name: 'HyperMotion License with a validity period of 3 months',
    code: 'SW-HYPERMOTION-LICENSE-WITH-A-VALIDITY-PER',
    listPrice: 105,
    category: 'Software License',
    description: 'License Type: HyperMotion License with a validity period of 3 months. VM Quantity: 1. Cost: 105.',
    sourceSheet: 'SoftwareList',
    sourceRow: 2
  },
  {
    id: 'tpl-product-3-hyperbdr-monthly-license',
    name: 'HyperBDR Monthly License',
    code: 'SW-HYPERBDR-MONTHLY-LICENSE',
    listPrice: 35,
    category: 'Software License',
    description: 'License Type: HyperBDR Monthly License. VM Quantity: 1. Cost: 35.',
    sourceSheet: 'SoftwareList',
    sourceRow: 3
  },
  {
    id: 'tpl-product-4-hyperbdr-yearly-license',
    name: 'HyperBDR Yearly License',
    code: 'SW-HYPERBDR-YEARLY-LICENSE',
    listPrice: 420,
    category: 'Software License',
    description: 'License Type: HyperBDR Yearly License. VM Quantity: 1. Cost: 420.',
    sourceSheet: 'SoftwareList',
    sourceRow: 4
  },
  {
    id: 'tpl-product-5-failback-license-one-time',
    name: 'Failback License (One-time)',
    code: 'SW-FAILBACK-LICENSE-ONE-TIME',
    listPrice: 14.9,
    category: 'Software License',
    description: 'License Type: Failback License (One-time). VM Quantity: 1. Cost: 14.9.',
    sourceSheet: 'SoftwareList',
    sourceRow: 5
  },
  {
    id: 'tpl-product-6-hyperbdr-saas-monthly-license-includi',
    name: 'HyperBDR SaaS Monthly License (including Failback License)',
    code: 'SW-HYPERBDR-SAAS-MONTHLY-LICENSE-INCLUDI',
    listPrice: 35,
    category: 'Software License',
    description: 'License Type: HyperBDR SaaS Monthly License (including Failback License). VM Quantity: 1. Cost: 35.',
    sourceSheet: 'SoftwareList',
    sourceRow: 6
  }
];

export const MOCK_SERVICES: Service[] = [
  {
    id: 'tpl-service-2-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (1 - 25 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 3795,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: 1 - 25. Cost: 3795.',
    quantityRange: '1 - 25',
    quantityMin: 1,
    quantityMax: 25,
    sourceSheet: 'OthersList',
    sourceRow: 2
  },
  {
    id: 'tpl-service-3-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (26 - 100 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 6095,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: 26 - 100. Cost: 6095.',
    quantityRange: '26 - 100',
    quantityMin: 26,
    quantityMax: 100,
    sourceSheet: 'OthersList',
    sourceRow: 3
  },
  {
    id: 'tpl-service-4-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (101 - 200 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 7590,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: 101 - 200. Cost: 7590.',
    quantityRange: '101 - 200',
    quantityMin: 101,
    quantityMax: 200,
    sourceSheet: 'OthersList',
    sourceRow: 4
  },
  {
    id: 'tpl-service-5-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (201 - 500 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 13800,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: 201 - 500. Cost: 13800.',
    quantityRange: '201 - 500',
    quantityMin: 201,
    quantityMax: 500,
    sourceSheet: 'OthersList',
    sourceRow: 5
  },
  {
    id: 'tpl-service-6-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (501 - 1000 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 25000,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: 501 - 1000. Cost: 25000.',
    quantityRange: '501 - 1000',
    quantityMin: 501,
    quantityMax: 1000,
    sourceSheet: 'OthersList',
    sourceRow: 6
  },
  {
    id: 'tpl-service-7-remote-professional-service-for-install',
    name: 'Remote Professional Service for Installation & Deployment (One-time) (>1000 VMs)',
    code: 'OT-REMOTE-PROFESSIONAL-SERVICE-FOR-INSTALL',
    listPrice: 0,
    unit: 'range',
    description: 'Description: Remote Professional Service for Installation & Deployment (One-time). VM Quantity: >1000. Cost: Contact Sales.',
    quantityRange: '>1000',
    quantityMin: 1001,
    quantityMax: 9999,
    pricingNote: 'Contact Sales',
    sourceSheet: 'OthersList',
    sourceRow: 7
  },
  {
    id: 'tpl-service-8-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (1 - 25 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 1800,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: 1 - 25. Cost: 1800.',
    quantityRange: '1 - 25',
    quantityMin: 1,
    quantityMax: 25,
    sourceSheet: 'OthersList',
    sourceRow: 8
  },
  {
    id: 'tpl-service-9-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (1 - 25 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 2300,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 1 - 25. Cost: 2300.',
    quantityRange: '1 - 25',
    quantityMin: 1,
    quantityMax: 25,
    sourceSheet: 'OthersList',
    sourceRow: 9
  },
  {
    id: 'tpl-service-10-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (26 - 100 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 65,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: 26 - 100. Cost: 65.',
    quantityRange: '26 - 100',
    quantityMin: 26,
    quantityMax: 100,
    sourceSheet: 'OthersList',
    sourceRow: 10
  },
  {
    id: 'tpl-service-11-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (26 - 100 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 90,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 26 - 100. Cost: 90.',
    quantityRange: '26 - 100',
    quantityMin: 26,
    quantityMax: 100,
    sourceSheet: 'OthersList',
    sourceRow: 11
  },
  {
    id: 'tpl-service-12-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (101 - 200 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 60,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: 101 - 200. Cost: 60.',
    quantityRange: '101 - 200',
    quantityMin: 101,
    quantityMax: 200,
    sourceSheet: 'OthersList',
    sourceRow: 12
  },
  {
    id: 'tpl-service-13-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (101 - 200 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 80,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 101 - 200. Cost: 80.',
    quantityRange: '101 - 200',
    quantityMin: 101,
    quantityMax: 200,
    sourceSheet: 'OthersList',
    sourceRow: 13
  },
  {
    id: 'tpl-service-14-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (201 - 500 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 55,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: 201 - 500. Cost: 55.',
    quantityRange: '201 - 500',
    quantityMin: 201,
    quantityMax: 500,
    sourceSheet: 'OthersList',
    sourceRow: 14
  },
  {
    id: 'tpl-service-15-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (201 - 500 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 70,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 201 - 500. Cost: 70.',
    quantityRange: '201 - 500',
    quantityMin: 201,
    quantityMax: 500,
    sourceSheet: 'OthersList',
    sourceRow: 15
  },
  {
    id: 'tpl-service-16-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (501 - 1000 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 50,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: 501 - 1000. Cost: 50.',
    quantityRange: '501 - 1000',
    quantityMin: 501,
    quantityMax: 1000,
    sourceSheet: 'OthersList',
    sourceRow: 16
  },
  {
    id: 'tpl-service-17-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (501 - 1000 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 65,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 501 - 1000. Cost: 65.',
    quantityRange: '501 - 1000',
    quantityMin: 501,
    quantityMax: 1000,
    sourceSheet: 'OthersList',
    sourceRow: 17
  },
  {
    id: 'tpl-service-18-remote-product-service-standard-7-12-op',
    name: 'Remote Product Service - Standard 7*12 (Optional, Yearly) (>1000 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-STANDARD-7-12-OP',
    listPrice: 0,
    unit: 'range',
    description: 'Description: Remote Product Service - Standard 7*12 (Optional, Yearly). VM Quantity: >1000. Cost: Contact Sales.',
    quantityRange: '>1000',
    quantityMin: 1001,
    quantityMax: 9999,
    pricingNote: 'Contact Sales',
    sourceSheet: 'OthersList',
    sourceRow: 18
  },
  {
    id: 'tpl-service-19-remote-product-service-premium-7-24-op',
    name: 'Remote Product Service - Premium 7*24 (Optional, Yearly) (>1000 VMs)',
    code: 'OT-REMOTE-PRODUCT-SERVICE-PREMIUM-7-24-OP',
    listPrice: 0,
    unit: 'range',
    description: 'Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: >1000. Cost: Contact Sales.',
    quantityRange: '>1000',
    quantityMin: 1001,
    quantityMax: 9999,
    pricingNote: 'Contact Sales',
    sourceSheet: 'OthersList',
    sourceRow: 19
  }
];

export const MOCK_DISCOUNTS: DiscountOption[] = [
  { id: 'disc-none', name: 'No Discount', percent: 0 },
  { id: 'disc-threshold-2-10', name: '> 100 VM (10% OFF)', percent: 10, condition: '> 100', threshold: 100, sourceSheet: 'Discount', sourceRow: 2 },
  { id: 'disc-threshold-3-15', name: '> 200 VM (15% OFF)', percent: 15, condition: '> 200', threshold: 200, sourceSheet: 'Discount', sourceRow: 3 },
  { id: 'disc-threshold-4-20', name: '> 300 VM (20% OFF)', percent: 20, condition: '> 300', threshold: 300, sourceSheet: 'Discount', sourceRow: 4 }
];

export const MOCK_QUOTATIONS: Quotation[] = [
  {
    id: 'q-01',
    quoteNo: 'QT-20260701-001',
    projectName: '华为云混合多云底座扩容项目',
    clientCompany: '深圳市腾讯计算机系统有限公司',
    contactPerson: '张建国',
    email: 'jianguo.zhang@tencent.com',
    region: '华南一区',
    industry: '互联网与新媒体',
    salesperson: '王丽华',
    createdByEmail: 'alice.chen@oneprocloud.com',
    currency: 'CNY',
    paymentTerms: '30%首付，60%实施验收付，10%质保金付款',
    status: 'Uploaded',
    items: [
      {
        id: 'item-101',
        type: 'Software',
        itemId: 'prod-01',
        name: '云原生容器云平台软件 V3.0',
        listPrice: 180000,
        discountPercent: 10,
        qty: 2,
        netUnitPrice: 162000,
        extendedPrice: 324000
      },
      {
        id: 'item-102',
        type: 'Service',
        itemId: 'serv-02',
        name: '系统私有化部署与集成实施服务',
        listPrice: 12000,
        discountPercent: 5,
        qty: 10,
        netUnitPrice: 11400,
        extendedPrice: 114000
      }
    ],
    softwareSubtotal: 324000,
    othersSubtotal: 114000,
    subtotalBeforeVat: 438000,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 438000,
    createdAt: '2026-07-01 14:32:00',
    feishuExcelFileToken: 'file_v3_a78bc34f9e80a76a5bde1234g',
    feishuExcelUrl: 'https://feishu.cn/file/file_v3_a78bc34f9e80a76a5bde1234g',
    feishuExcelPath: '/我的云盘/报价单归档/2026Q3/Quote-QT-20260701-001.xlsx',
    feishuExcelUploadedAt: '2026-07-01 14:45:12',
    feishuFileToken: 'file_v3_a78bc34f9e80a76a5bde1234g',
    feishuUrl: 'https://feishu.cn/file/file_v3_a78bc34f9e80a76a5bde1234g',
    feishuPath: '/我的云盘/报价单归档/2026Q3/Quote-QT-20260701-001.xlsx',
    feishuUploadedAt: '2026-07-01 14:45:12'
  },
  {
    id: 'q-02',
    quoteNo: 'QT-20260702-004',
    projectName: '中国银行核心数据库数据网格改造',
    clientCompany: '中国银行股份有限公司北京市分行',
    contactPerson: '刘少坤',
    email: 'shao_kun.liu@boc.cn',
    region: '华北一区',
    industry: '金融服务业',
    salesperson: '李向东',
    createdByEmail: 'bob.wang@oneprocloud.com',
    currency: 'CNY',
    paymentTerms: '合同签订付50%，部署完毕付50%',
    status: 'Generated',
    items: [
      {
        id: 'item-201',
        type: 'Software',
        itemId: 'prod-02',
        name: '智能数据网格中台系统 V2.1',
        listPrice: 250000,
        discountPercent: 15,
        qty: 1,
        netUnitPrice: 212500,
        extendedPrice: 212500
      },
      {
        id: 'item-202',
        type: 'Service',
        itemId: 'serv-01',
        name: '架构规划与深度专家咨询服务',
        listPrice: 15000,
        discountPercent: 10,
        qty: 5,
        netUnitPrice: 13500,
        extendedPrice: 67500
      },
      {
        id: 'item-203',
        type: 'Other',
        itemId: 'custom',
        name: '定制化硬件承载服务器租用',
        listPrice: 15000,
        discountPercent: 0,
        qty: 2,
        netUnitPrice: 15000,
        extendedPrice: 30000
      }
    ],
    softwareSubtotal: 212500,
    othersSubtotal: 97500,
    subtotalBeforeVat: 310000,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 310000,
    createdAt: '2026-07-02 09:15:30'
  },
  {
    id: 'q-03',
    quoteNo: 'QT-20260703-009',
    projectName: '顺丰控股大模型客服微调底座采购',
    clientCompany: '顺丰速运有限公司深圳总部',
    contactPerson: '陈志远',
    email: 'zhiyuan.chen@sf-express.com',
    region: '华南一区',
    industry: '物流与供应链',
    salesperson: '王丽华',
    createdByEmail: 'alice.chen@oneprocloud.com',
    currency: 'CNY',
    paymentTerms: '分期付款（3-3-3-1比例）',
    status: 'Uploaded',
    items: [
      {
        id: 'item-301',
        type: 'Software',
        itemId: 'prod-04',
        name: '大语言模型私有化部署底座 V4.0',
        listPrice: 420000,
        discountPercent: 20,
        qty: 1,
        netUnitPrice: 336000,
        extendedPrice: 336000
      },
      {
        id: 'item-302',
        type: 'Service',
        itemId: 'serv-05',
        name: '定制化功能二次开发与调试服务',
        listPrice: 8000,
        discountPercent: 10,
        qty: 15,
        netUnitPrice: 7200,
        extendedPrice: 108000
      },
      {
        id: 'item-303',
        type: 'Service',
        itemId: 'serv-04',
        name: '企业级 7x24 终极售后保障年费',
        listPrice: 60000,
        discountPercent: 15,
        qty: 1,
        netUnitPrice: 51000,
        extendedPrice: 51000
      }
    ],
    softwareSubtotal: 336000,
    othersSubtotal: 159000,
    subtotalBeforeVat: 495000,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 495000,
    createdAt: '2026-07-03 16:40:00',
    feishuExcelFileToken: 'file_v3_99cf76e1a4de1ab34fe29088k',
    feishuExcelUrl: 'https://feishu.cn/file/file_v3_99cf76e1a4de1ab34fe29088k',
    feishuExcelPath: '/我的云盘/报价单归档/2026Q3/Quote-QT-20260703-009.xlsx',
    feishuExcelUploadedAt: '2026-07-03 17:12:05',
    feishuFileToken: 'file_v3_99cf76e1a4de1ab34fe29088k',
    feishuUrl: 'https://feishu.cn/file/file_v3_99cf76e1a4de1ab34fe29088k',
    feishuPath: '/我的云盘/报价单归档/2026Q3/Quote-QT-20260703-009.xlsx',
    feishuUploadedAt: '2026-07-03 17:12:05'
  },
  {
    id: 'q-04',
    quoteNo: 'QT-20260704-002',
    projectName: '国家电网分布式安全网关测试部署',
    clientCompany: '国家电网公司上海市电力公司',
    contactPerson: '杨红卫',
    email: 'hongwei.yang@sh.sgcc.com.cn',
    region: '华东一区',
    industry: '能源与公共事业',
    salesperson: '张国强',
    createdByEmail: 'david.liu@oneprocloud.com',
    currency: 'CNY',
    paymentTerms: '货到付款 100%',
    status: 'Draft',
    items: [
      {
        id: 'item-401',
        type: 'Software',
        itemId: 'prod-03',
        name: '零信任安全访问控制网关 V1.5',
        listPrice: 85000,
        discountPercent: 5,
        qty: 3,
        netUnitPrice: 80750,
        extendedPrice: 242250
      },
      {
        id: 'item-402',
        type: 'Service',
        itemId: 'serv-02',
        name: '系统私有化部署与集成实施服务',
        listPrice: 12000,
        discountPercent: 5,
        qty: 4,
        netUnitPrice: 11400,
        extendedPrice: 45600
      }
    ],
    softwareSubtotal: 242250,
    othersSubtotal: 45600,
    subtotalBeforeVat: 287850,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 287850,
    createdAt: '2026-07-04 11:22:15'
  },
  {
    id: 'q-05',
    quoteNo: 'QT-20260705-015',
    projectName: '美团外卖高并发 CI/CD 流水线落地',
    clientCompany: '北京三快在线科技有限公司',
    contactPerson: '梁超群',
    email: 'liangchaoqun@meituan.com',
    region: '华北一区',
    industry: '互联网与新媒体',
    salesperson: '李向东',
    createdByEmail: 'bob.wang@oneprocloud.com',
    currency: 'CNY',
    paymentTerms: '合同签订支付100%',
    status: 'Draft',
    items: [
      {
        id: 'item-501',
        type: 'Software',
        itemId: 'prod-05',
        name: 'DevOps 自动化交付流水线 V5.0',
        listPrice: 120000,
        discountPercent: 20,
        qty: 2,
        netUnitPrice: 96000,
        extendedPrice: 192000
      },
      {
        id: 'item-502',
        type: 'Service',
        itemId: 'serv-03',
        name: '高级研发运维专家驻场技术支持',
        listPrice: 10000,
        discountPercent: 10,
        qty: 8,
        netUnitPrice: 9000,
        extendedPrice: 72000
      }
    ],
    softwareSubtotal: 192000,
    othersSubtotal: 72000,
    subtotalBeforeVat: 264000,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 264000,
    createdAt: '2026-07-05 15:10:45'
  }
];

export const MOCK_REGIONS = ['华东一区', '华北一区', '华南一区', '华中一区', '西南一区', '海外一区'];
export const MOCK_INDUSTRIES = ['金融服务业', '互联网与新媒体', '制造与重工业', '物流与供应链', '能源与公共事业', '政府与医疗健康'];
export const MOCK_SALESPERSONS = ['王丽华', '李向东', '张国强', '林志明'];
