import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import {
  getAvailablePlatforms,
  getCurrentPlatformKey,
  getLandingPath,
} from '../src/utils/platformAccess.js'

const router = fs.readFileSync(
  new URL('../src/router/index.js', import.meta.url),
  'utf8',
)
const sidebar = fs.readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8',
)
const platformAccess = fs.readFileSync(
  new URL('../src/utils/platformAccess.js', import.meta.url),
  'utf8',
)
const invoiceApi = fs.readFileSync(
  new URL('../src/modules/quotation/api/invoices.ts', import.meta.url),
  'utf8',
)
const quotationApp = fs.readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const customerCenter = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/CustomerCenter.vue',
    import.meta.url,
  ),
  'utf8',
)
const customerApi = fs.readFileSync(
  new URL('../src/modules/quotation/api/customers.ts', import.meta.url),
  'utf8',
)
const invoiceCreate = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoiceCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const invoicePreview = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoicePreview.vue',
    import.meta.url,
  ),
  'utf8',
)
const invoiceList = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoiceList.vue',
    import.meta.url,
  ),
  'utf8',
)
const invoiceDetail = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoiceDetail.vue',
    import.meta.url,
  ),
  'utf8',
)
const invoiceDetailsDrawer = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoiceDetailsDrawer.vue',
    import.meta.url,
  ),
  'utf8',
)
const invoicePdfRenderer = fs.readFileSync(
  new URL(
    '../../backend/invoice/services/pdf_renderer.py',
    import.meta.url,
  ),
  'utf8',
)
const invoicePermissionsApi = fs.readFileSync(
  new URL(
    '../src/modules/quotation/api/invoicePermissions.ts',
    import.meta.url,
  ),
  'utf8',
)
const userPermissionSection = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/UserPermissionSection.vue',
    import.meta.url,
  ),
  'utf8',
)
const permissionPage = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/ViewPermissionPage.vue',
    import.meta.url,
  ),
  'utf8',
)
const baseDatePicker = fs.readFileSync(
  new URL('../src/components/ui/BaseDatePicker.vue', import.meta.url),
  'utf8',
)
const appEn = JSON.parse(fs.readFileSync(
  new URL('../src/locales/en.json', import.meta.url),
  'utf8',
))
const appZh = JSON.parse(fs.readFileSync(
  new URL('../src/locales/zh-CN.json', import.meta.url),
  'utf8',
))
const quotationZh = JSON.parse(fs.readFileSync(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8',
))
const quotationEn = JSON.parse(fs.readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
))

test('Sales routes stay inside Quote Desk and require sales access', () => {
  assert.match(router, /\/quotation\/sales\/dashboard/)
  assert.match(router, /\/quotation\/sales\/invoices/)
  assert.match(router, /\/quotation\/sales\/invoices\/:invoiceId/)
  assert.match(router, /\/quotation\/sales\/create/)
  assert.match(router, /requiredFeature: 'sales_management'/)
})

test('Quote Desk navigation exposes separate Quote and Sales sections', () => {
  assert.match(sidebar, /quotation\.quoteSection/)
  assert.match(sidebar, /quotation\.salesSection/)
  assert.match(sidebar, /userHasFeature\('sales_management'\)/)
  assert.match(sidebar, /\/quotation\/sales\/create/)
})

test('Quote Desk access navigation is restricted to Quote admins', () => {
  assert.match(sidebar, /userStore\.userHasQuotationAdminAccess\(\)/)
  assert.match(router, /requiredQuotationAdmin: true/)
})

test('Invoice navigation mirrors the Quote section naming hierarchy', () => {
  assert.equal(appEn.quotation.salesSection, 'Invoice')
  assert.equal(appEn.quotation.salesDashboard, 'Overview')
  assert.equal(appEn.quotation.createInvoice, 'New Invoice')
  assert.equal(quotationEn.quotation.sales.create.title, 'New Invoice')
  assert.equal(appZh.quotation.salesSection, '发票')
  assert.equal(appZh.quotation.salesDashboard, '发票看板')
  assert.equal(appZh.quotation.createInvoice, '新建发票')
})

test('Invoice English copy uses customer-facing accounting terminology', () => {
  const sales = quotationEn.quotation.sales
  const create = sales.create
  const fields = sales.fields

  assert.equal(sales.dashboardTitle, 'Invoice overview')
  assert.equal(sales.trendGranularityLabel, 'Trend interval')
  assert.equal(sales.invoiceValue, 'Invoice amount')
  assert.equal(sales.salesOwner, 'Account owner')
  assert.equal(sales.filters.invoiceContact, 'Billing contact')
  assert.equal(fields.contactPerson, 'Billing contact')
  assert.equal(fields.contactEmail, 'Billing contact email')
  assert.equal(create.invoiceInformation, 'Invoice details')
  assert.equal(create.enquiryEmail, 'Contact email')
  assert.equal(create.contactAndPayment, 'Contact and payment details')
  assert.equal(create.product, 'Internal product')
  assert.equal(create.salesOwner, 'Account owner')
  assert.equal(create.bankHistory, 'Saved bank details')
  assert.equal(create.bankHistoryPlaceholder, 'Select saved bank details')
  assert.equal(create.generateAndIssue, 'Issue invoice')
})

test('Chinese Quote Desk copy does not mix in Sales or Invoice labels', () => {
  assert.doesNotMatch(
    JSON.stringify(appZh.quotation),
    /\b(?:Invoice|Sales)\b/,
  )
  assert.doesNotMatch(
    JSON.stringify(quotationZh.quotation),
    /\b(?:Invoice|Sales)\b/,
  )
})

test('Quote and Sales are collapsible while shared links stay top-level', () => {
  assert.match(sidebar, /toggleQuotationMenu/)
  assert.match(sidebar, /toggleSalesMenu/)
  assert.match(sidebar, /quotationMenuOpen/)
  assert.match(sidebar, /salesMenuOpen/)
  assert.match(sidebar, /:aria-expanded=/)
  assert.match(sidebar, /class="nav-item quotation-shared-link"/)
  assert.doesNotMatch(sidebar, /toggleSharedMenu|sharedMenuOpen/)
  assert.doesNotMatch(sidebar, /quotation\.sharedSection/)
})

test('Invoice users can open shared customer, catalog, and audit links', () => {
  assert.match(sidebar, /userStore\.userHasFeature\('sales_management'\)/)
  assert.match(router, /requiredAnyFeatures: \['quotation_management', 'sales_management'\]/)
})

test('Customers combines quotation and parsed invoice contacts', () => {
  assert.match(quotationApp, /getCustomerSummary/)
  assert.match(quotationApp, /:customers="customerSummary"/)
  assert.match(quotationApp, /async function loadCustomers\(\)/)
  assert.match(customerCenter, /customers: Customer\[\]/)
  assert.match(customerApi, /record_count/)
  assert.match(customerApi, /updated_at/)
})

test('Invoice permission is an internal Quote Desk capability', () => {
  assert.doesNotMatch(platformAccess, /key: 'sales_management'/)
  assert.match(platformAccess, /sales_management: 'quotation_management'/)
  assert.match(platformAccess, /\/quotation\/sales\/dashboard/)
})

test('Invoice access does not create a standalone platform', () => {
  assert.match(platformAccess, /function getLandingPath\(user\)/)
  assert.doesNotMatch(platformAccess, /key: 'sales_management'/)
})

test('Invoice-only users still receive Quote Desk as their platform', () => {
  const user = {
    access_profile: {
    visible_features: ['workspace', 'sales_management'],
      available_platforms: [
        { key: 'workspace', default_path: '/dashboard' },
        {
          key: 'sales_management',
          default_path: '/quotation/sales/dashboard',
        },
      ],
      preferred_platform: 'workspace',
      invoice_access: {
        enabled: true,
        role: 'invoice_user',
        capabilities: ['view', 'edit', 'import', 'issue'],
      },
    },
  }
  const platforms = getAvailablePlatforms(user)
  assert.deepEqual(
    platforms.map((platform) => platform.key),
    ['workspace', 'quotation_management'],
  )
  assert.equal(getLandingPath(user), '/dashboard')
})

test('Invoice routes identify Quote Desk as the current platform', () => {
  assert.equal(
    getCurrentPlatformKey('/quotation/sales/invoices'),
    'quotation_management',
  )
  assert.equal(
    getCurrentPlatformKey('/quotation/dashboard'),
    'quotation_management',
  )
})

test('Invoice routes use the Quote Desk navigation shell', () => {
  assert.match(
    sidebar,
    /\['quotation_management', 'sales_management'\]\.includes\(/,
  )
})

test('Quote and Invoice roles use clearly different status colors', () => {
  assert.match(userPermissionSection, /role === 'quotation_admin' \|\| role === 'invoice_admin'/)
  assert.match(userPermissionSection, /bg-indigo-700/)
  assert.match(userPermissionSection, /bg-sky-400/)
  assert.doesNotMatch(userPermissionSection, /role === 'quotation_user' \|\| role === 'invoice_user'.*bg-blue-400/)
})

test('Invoice access is managed inside the existing authorization page', () => {
  assert.match(
    invoicePermissionsApi,
    /\/v1\/invoice\/access-permissions/,
  )
  assert.match(permissionPage, /UserPermissionSection/)
  assert.match(permissionPage, /grantInvoiceAccess/)
  assert.match(permissionPage, /revokeInvoiceAccess/)
  assert.match(userPermissionSection, /invoiceColumn/)
  assert.match(userPermissionSection, /platformOff/)
  assert.match(userPermissionSection, /invoiceRoleOptions/)
  assert.match(userPermissionSection, /InvoiceAccessRole/)
  assert.match(
    invoicePermissionsApi,
    /'invoice_user' \| 'invoice_admin'/,
  )
  assert.match(invoicePermissionsApi, /role: InvoiceAccessRole/)
  assert.match(userPermissionSection, /<select/)
  assert.match(userPermissionSection, /saveWorkspaceAccess/)
})

test('Invoice access table stays compact with two roles', () => {
  assert.match(userPermissionSection, /invoiceRoleUser/)
  assert.match(userPermissionSection, /invoiceRoleAdmin/)
  assert.doesNotMatch(
    userPermissionSection,
    /invoiceRoleViewer|invoiceRoleOperator|invoiceRoleManager/,
  )
  assert.doesNotMatch(userPermissionSection, /assignedByColumn/)
  assert.doesNotMatch(userPermissionSection, /min-w-\[1320px\]/)
  assert.match(userPermissionSection, /table-fixed/)
})

test('Invoice creation does not ask users to enter a manual sales region', () => {
  assert.doesNotMatch(invoiceCreate, /salesRegion/)
  assert.doesNotMatch(invoiceCreate, /form\.region/)
})

test('Invoice creation does not expose internal sales information', () => {
  assert.doesNotMatch(invoiceCreate, /internalInformation/)
})

test('Invoice list keeps a usable horizontal scrollbar for wide tables', () => {
  assert.match(invoiceList, /overflow-x-auto/)
  assert.doesNotMatch(invoiceList, /overflow-x-hidden/)
})

test('Invoice actions and routes use effective capabilities', () => {
  assert.match(platformAccess, /hasInvoiceCapability/)
  assert.match(router, /requiredInvoiceCapability: 'edit'/)
  assert.match(sidebar, /userHasInvoiceCapability\('edit'\)/)
  assert.match(invoiceCreate, /userHasInvoiceCapability\('issue'\)/)
  assert.match(invoiceList, /userHasInvoiceCapability\('issue'\)/)
})

test('Invoice draft validation surfaces wrapped API errors', () => {
  assert.match(invoiceCreate, /responseData\?\.data/)
  assert.match(invoiceCreate, /Object\.values\(errorData\)/)
})

test('Feishu Invoice sync remains available to background automation', () => {
  assert.match(invoiceApi, /function startInvoiceSync/)
  assert.match(invoiceApi, /function getInvoiceSyncStatus/)
  assert.doesNotMatch(invoiceList, /type="file"/)
  assert.doesNotMatch(router, /\/quotation\/sales\/imports\//)
  assert.doesNotMatch(invoiceList, /pendingImports/)
})

test('Invoice list relies on background sync without manual controls', () => {
  assert.doesNotMatch(invoiceList, /startInvoiceSync/)
  assert.doesNotMatch(invoiceList, /getInvoiceSyncStatus/)
  assert.doesNotMatch(invoiceList, /handleSync/)
  assert.doesNotMatch(invoiceList, /syncInvoices/)
  assert.doesNotMatch(invoiceList, /@click="loadInvoices"/)
})

test('Invoice rows open a drawer and keep actions icon-only', () => {
  assert.match(invoiceList, /InvoiceDetailsDrawer/)
  assert.match(invoiceList, /selectedInvoiceId/)
  assert.match(invoiceList, /@click="handleRowClick\(invoice, \$event\)"/)
  assert.match(invoiceList, /@keydown\.enter="openInvoiceDetails\(invoice\)"/)
  assert.match(
    invoiceList,
    /@keydown\.space\.prevent="openInvoiceDetails\(invoice\)"/,
  )
  assert.match(invoiceList, /invoice\.feishu_url/)
  assert.match(invoiceList, /<ExternalLink/)
  assert.match(invoiceList, /@click\.stop="handleDownload\(invoice\)"/)
  assert.doesNotMatch(
    invoiceList,
    /<router-link[\s\S]{0,180}invoice\.invoice_no/,
  )
})

test('Invoice list only labels manually saved drafts and keeps dates on one line', () => {
  assert.match(
    invoiceList,
    /invoice\.status === InvoiceStatus\.DRAFT[\s\S]{0,100}invoice\.source_type === 'manual'/,
  )
  assert.match(
    invoiceList,
    /columnIsVisible\('invoiceDate'\)[\s\S]{0,180}whitespace-nowrap/,
  )
  assert.match(invoiceList, /invoiceDate: \{ label: 'invoiceDate', width: 130/)
})

test('Invoice actions stay in the list and details remain read-only', () => {
  assert.match(invoiceList, /quotation\.sales\.copyInvoice/)
  assert.match(invoiceList, /quotation\.sales\.editInvoice/)
  assert.match(invoiceList, /quotation\.sales\.create\.generateAndIssue/)
  assert.match(invoiceList, /query:\s*\{\s*copy:/)
  assert.doesNotMatch(invoiceDetail, /quotation\.sales\.copyInvoice/)
  assert.doesNotMatch(invoiceDetail, /quotation\.sales\.editDraft/)
  assert.doesNotMatch(
    invoiceDetail,
    /quotation\.sales\.create\.generateAndIssue/,
  )
})

test('Invoice details keep the in-product formal document preview', () => {
  assert.match(invoiceDetail, /<InvoicePreview :invoice="previewInvoice"/)
  assert.doesNotMatch(invoiceDetail, /<iframe/)
  assert.doesNotMatch(invoiceDetail, /sourcePdfUrl/)
})

test('Delivery note preview uses its own non-commercial layout', () => {
  assert.match(invoiceDetail, /documentKind: record\.document_kind/)
  assert.match(invoicePreview, /invoice\.documentKind === 'delivery_note'/)
  assert.match(invoicePreview, />Delivery Note</)
  assert.match(invoicePreview, /Date of Delivery/)
  assert.doesNotMatch(
    invoicePreview,
    /invoice\.documentKind === 'delivery_note'[\s\S]{0,500}Total Amount:/,
  )
})

test('Proforma invoice preview keeps its document identity', () => {
  assert.match(invoicePreview, /invoice\.documentKind === 'proforma_invoice'/)
  assert.match(invoicePreview, />\s*Proforma Invoice\s*<\/h2>/)
  assert.match(invoicePreview, /Proforma Invoice Number/)
})

test('Invoice item descriptions preserve source line breaks', () => {
  assert.match(
    invoicePreview,
    /\.invoice-items-table td:nth-child\(2\)[\s\S]{0,120}white-space:\s*pre-line/,
  )
})

test('Invoice creation reuses the shared product-line catalog and copy prefill', () => {
  assert.match(invoiceApi, /product_line:\s*string/)
  assert.match(invoiceCreate, /getCatalog/)
  assert.match(invoiceCreate, /updateCatalog/)
  assert.match(invoiceCreate, /isProductLinePrefixValid/)
  assert.match(invoiceCreate, /route\.query\.copy/)
  assert.match(invoiceCreate, /InvoiceNumberingMode\.AUTO/)
  assert.match(invoiceCreate, /todayInputValue\(\)/)
})

test('Invoice creation offers parsed history without mixing contact roles', () => {
  assert.match(invoiceApi, /function getInvoiceFormContext/)
  assert.match(invoiceCreate, /getInvoiceFormContext/)
  assert.match(invoiceCreate, /HistoryTextInput/)
  assert.match(invoiceCreate, /customerContactPerson/)
  assert.match(invoiceCreate, /customerContactEmail/)
  assert.match(invoiceCreate, /customer_contact_person:/)
  assert.match(invoiceCreate, /customer_contact_email:/)
  assert.match(invoiceCreate, /handleCustomerSelect/)
  assert.match(invoiceCreate, /handleItemDescriptionSelect/)
  assert.match(invoiceCreate, /item\.unitPrice/)
})

test('Invoice creation offers complete parsed bank-account history', () => {
  assert.match(invoiceCreate, /bankHistoryOptions/)
  assert.match(invoiceCreate, /handleBankHistorySelect/)
  assert.match(invoiceCreate, /bankAccountName/)
  assert.match(invoiceCreate, /bankSwiftCode/)
  assert.match(invoiceCreate, /remittanceInstruction/)
  assert.match(invoiceCreate, /invoice-bank-account-history/)
})

test('Invoice payment terms support presets and custom values', () => {
  assert.match(invoiceCreate, /test-id="invoice-payment-terms"/)
  assert.match(invoiceCreate, /:options="paymentTermOptions"/)
  assert.match(invoiceCreate, /function normalizePaymentTerm\(value: string\)/)
  assert.match(
    invoiceCreate,
    /return paymentTermOptions\.some[\s\S]*normalized \|\| 'CIA'/,
  )
  assert.doesNotMatch(
    invoiceCreate,
    /<FormSelect\s+\n\s+v-model="form\.paymentTerms"/,
  )
})

test('Invoice bank fields offer parsed history without a standalone remarks input', () => {
  const bankFieldHistoryIds = [
    'invoice-bank-account-name-history',
    'invoice-bank-name-history',
    'invoice-bank-address-history',
    'invoice-bank-account-number-history',
    'invoice-bank-code-history',
    'invoice-bank-branch-code-history',
    'invoice-bank-swift-code-history',
    'invoice-remittance-instruction-history',
  ]

  for (const testId of bankFieldHistoryIds) {
    assert.match(invoiceCreate, new RegExp(testId))
  }
  assert.doesNotMatch(
    invoiceCreate,
    /<span>\{\{ t\('quotation\.sales\.create\.remarks'\) \}\}<\/span>/,
  )
  assert.doesNotMatch(invoicePdfRenderer, /_plain\(invoice\.remarks/)
  assert.match(invoiceCreate, /selectedBankAccount/)
  assert.doesNotMatch(invoiceCreate, /v-model="form\.bankName"[\s\S]*invoice-bank-account-history/)
})

test('Invoice numbering appears before the product-line selector', () => {
  assert.ok(
    invoiceCreate.indexOf('quotation.sales.create.numberingMode') <
      invoiceCreate.indexOf('quotation.pages.create.productLine'),
  )
})

test('Invoice list reuses 10, 20 and 50 row pagination', () => {
  assert.match(invoiceApi, /page\?: number/)
  assert.match(invoiceApi, /pageSize\?: 10 \| 20 \| 50/)
  assert.match(invoiceApi, /page: params\.page/)
  assert.match(invoiceApi, /page_size: params\.pageSize/)
  assert.match(invoiceList, /const pageSizeOptions = \[10, 20, 50\]/)
  assert.match(invoiceList, /handlePageSizeChange/)
  assert.match(invoiceList, /requestPage/)
  assert.match(invoiceList, /totalPages/)
})

test('Invoice list columns support pointer and keyboard resizing', () => {
  assert.match(invoiceList, /const columnWidths = ref/)
  assert.match(invoiceList, /<colgroup>/)
  assert.match(invoiceList, /width: '100%'/)
  assert.match(invoiceList, /minWidth: `\$\{invoiceTableWidth\}px`/)
  assert.match(invoiceList, /data-column-resizer/)
  assert.match(invoiceList, /startColumnResize/)
  assert.match(invoiceList, /handleColumnResize/)
  assert.match(invoiceList, /resizeColumnBy/)
  assert.match(invoiceList, /@keydown\.left\.stop\.prevent/)
  assert.match(invoiceList, /@keydown\.right\.stop\.prevent/)
})

test('Invoice list filters sales records through backend query parameters', () => {
  for (const parameter of [
    'customer',
    'invoice_contact',
    'invoice_contact_email',
    'region',
    'sales_owner',
    'status',
    'source_type',
    'currency',
    'invoice_from',
    'invoice_to',
  ]) {
    assert.match(invoiceApi, new RegExp(`${parameter}:`))
  }
  assert.match(invoiceList, /data-invoice-filters/)
  assert.match(invoiceList, /selectedInvoiceContact/)
  assert.match(invoiceList, /invoiceContactOptions/)
  assert.match(invoiceList, /allInvoiceContacts/)
  assert.match(invoiceList, /selectedCurrency/)
  assert.match(invoiceList, /currencyOptions/)
  assert.match(invoiceList, /allCurrencies/)
  assert.doesNotMatch(invoiceList, /selectedSource/)
  assert.doesNotMatch(invoiceList, /sourceOptions/)
  assert.doesNotMatch(invoiceList, /label: contact\.email/)
  assert.doesNotMatch(invoiceList, /selectedStatus/)
  assert.doesNotMatch(invoiceList, /statusOptions/)
  assert.doesNotMatch(invoiceList, /columnIsVisible\('status'\)/)
  assert.match(invoiceList, /InvoiceStatus\.DRAFT/)
  assert.match(invoiceList, /BaseDatePicker/)
  assert.match(invoiceList, /visibleInvoiceColumns/)
  assert.match(invoiceList, /data-invoice-column-picker/)
  assert.match(invoiceList, /defaultInvoiceColumns/)
  assert.match(invoiceList, /contactEmail/)
  assert.match(invoiceList, /customerAddress/)
  assert.match(invoiceList, /invoice\.contact_email/)
  assert.match(invoiceList, /invoice\.customer_address/)
  assert.match(invoiceList, /class="dm-card overflow-visible"/)
  assert.doesNotMatch(invoiceList, /class="dm-card overflow-hidden"/)
  assert.match(invoiceList, /dm-input h-9 w-full py-1\.5 !pl-9 !pr-9/)
  assert.match(baseDatePicker, /!pl-9 !pr-9/)
  assert.doesNotMatch(invoiceList, /selectedCustomer/)
  assert.doesNotMatch(invoiceList, /selectedRegion/)
  assert.doesNotMatch(invoiceList, /selectedSalesOwner/)
  assert.doesNotMatch(invoiceList, /columnIsVisible\('region'\)/)
  assert.doesNotMatch(invoiceList, /columnIsVisible\('salesOwner'\)/)
  assert.doesNotMatch(invoiceList, /columnIsVisible\('paymentTerms'\)/)
  assert.doesNotMatch(invoiceList, /filteredInvoices/)
})

test('Invoice numeric and action headers align with their cells', () => {
  assert.match(invoiceList, /column\.key === 'total'/)
  assert.match(
    invoiceList,
    /<th class="!text-right">\{\{ t\('quotation\.sales\.actions'\) \}\}<\/th>/,
  )
})

test('Create Invoice saves drafts and issued records through the API', () => {
  assert.match(invoiceApi, /function createInvoice/)
  assert.match(invoiceApi, /apiClient\.post\('\/v1\/invoice\/invoices'/)
  assert.match(invoiceCreate, /createInvoice/)
  assert.match(invoiceCreate, /InvoiceStatus\.DRAFT/)
  assert.match(invoiceCreate, /InvoiceStatus\.ISSUED/)
  assert.match(invoiceCreate, /SignaturePicker/)
})

test('Create Invoice keeps the add-item action after the item list', () => {
  const itemListIndex = invoiceCreate.indexOf(
    'v-for="(item, index) in form.items"',
  )
  const addItemIndex = invoiceCreate.indexOf(
    'data-testid="invoice-add-item"',
  )
  const totalIndex = invoiceCreate.indexOf(
    "t('quotation.sales.create.totalAmount')",
  )

  assert.notEqual(itemListIndex, -1)
  assert.notEqual(addItemIndex, -1)
  assert.notEqual(totalIndex, -1)
  assert.ok(addItemIndex > itemListIndex)
  assert.ok(addItemIndex < totalIndex)
  assert.match(
    invoiceCreate,
    /data-testid="invoice-add-item"[\s\S]*?w-full[\s\S]*?@click="addItem"/,
  )
})

test('Invoice numbering supports locked automatic and custom modes', () => {
  assert.match(invoiceApi, /InvoiceNumberingMode/)
  assert.match(invoiceApi, /numbering_mode/)
  assert.match(invoiceCreate, /InvoiceNumberingMode\.AUTO/)
  assert.match(invoiceCreate, /InvoiceNumberingMode\.CUSTOM/)
  assert.match(invoiceCreate, /:disabled="isEditing"/)
  assert.match(invoiceCreate, /:readonly="form\.numberingMode ===/)
})

test('Draft invoices can be edited and issued without creating duplicates', () => {
  assert.match(router, /\/quotation\/sales\/invoices\/:invoiceId\/edit/)
  assert.match(invoiceApi, /function updateInvoice/)
  assert.match(invoiceApi, /apiClient\.patch/)
  assert.match(invoiceCreate, /getInvoice/)
  assert.match(invoiceCreate, /updateInvoice/)
  assert.match(invoiceCreate, /InvoiceStatus\.DRAFT/)
  assert.match(invoiceList, /invoice\.status === InvoiceStatus\.DRAFT/)
  assert.match(invoiceList, /\/edit`/)
})

test('Invoice preview remains an approved English commercial document', () => {
  assert.match(invoicePreview, /data-document-language="en"/)
  assert.match(invoicePreview, /Commercial Invoice/)
  assert.match(invoicePreview, /Bill to/)
  assert.match(invoicePreview, /Additional Notes &amp; Disclaimers/)
  assert.match(invoicePreview, /SWIFT Code/)
  assert.doesNotMatch(invoicePreview, /sales_owner|Sales Region/)
})

test('Issued PDF downloads are exposed only when the backend confirms one', () => {
  assert.match(invoiceApi, /function downloadInvoicePdf/)
  assert.match(invoiceApi, /responseType: 'blob'/)
  assert.match(invoiceList, /invoice\.pdf_available/)
  assert.match(invoiceList, /downloadInvoicePdf/)
})

test('Invoice detail reuses the approved preview as a read-only drawer', () => {
  assert.match(invoiceApi, /function getInvoice/)
  assert.match(invoiceDetailsDrawer, /<InvoiceDetail/)
  assert.match(invoiceDetailsDrawer, /embedded/)
  assert.match(invoiceDetail, /InvoicePreview/)
  assert.doesNotMatch(invoiceDetail, /invoice\.pdf_available/)
  assert.doesNotMatch(invoiceDetail, /downloadInvoicePdf/)
})

test('Embedded Invoice details omit redundant hero and summary cards', () => {
  assert.match(invoiceDetail, /<template v-if="!embedded">/)
  assert.match(invoiceDetail, /<header class="dm-card/)
  assert.match(invoiceDetail, /grid gap-3 sm:grid-cols-2 xl:grid-cols-4/)
})
