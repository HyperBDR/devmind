/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { Product, Service, DiscountOption } from './types';

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
export const MOCK_SALESPERSONS = ['王丽华', '李向东', '张国强', '林志明'];
