import { expect, test } from '@playwright/test'

async function setupAuthenticatedSession(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'e2e-token')
    window.localStorage.setItem('userLanguage', 'en')
  })
  await page.route('**/api/v1/auth/user', (route) =>
    route.fulfill({
      json: {
        id: 1,
        username: 'admin',
        email: 'admin@example.com',
        is_staff: true,
        profile: { nickname: 'admin', bio: '' },
        access_profile: {
          visible_features: ['quotation_management'],
          available_platforms: [
            { key: 'quotation_management', default_path: '/quotation/list' },
          ],
          landing_path: '/quotation/list',
        },
      },
    }),
  )
  await page.route('**/api/v1/quotation/catalog', (route) =>
    route.fulfill({
      json: {
        version: 'test',
        initialized: true,
        products: [],
        services: [],
        discounts: [],
        product_lines: [{ value: 'BDR', label: 'BDR' }],
        payment_terms: [{ value: 'NET 30', label: 'NET 30' }],
      },
    }),
  )
}

const candidate = {
  quote_no: 'PARSE-DEMO-001',
  product_line: 'BDR',
  project_name: 'Document Parsing Demo',
  currency: 'USD',
  payment_term_option: 'NET 30',
  payment_terms: 'NET 30',
  quote_date: '2026-07-22',
  expire_date: '2026-08-21',
  tax_label: 'VAT',
  vat_rate: '8',
  remarks_disclaimer: '',
  issuer_company_name: 'OnePro Cloud Limited',
  issuer_contact_name: 'QA Sales',
  issuer_contact_email: 'sales@example.com',
  issuer_contact_title: 'Sales Manager',
  client_company: 'QA Customer',
  contact_person: 'QA Contact',
  email: 'customer@example.com',
  billing_company: 'QA Customer',
  billing_contact: 'QA Contact',
  billing_email: 'customer@example.com',
  items: [
    {
      line_no: 1,
      type: 'Software',
      description: 'HyperMotion subscription',
      qty: '1',
      list_price: '1000',
      discount_percent: '0',
      net_unit_price: '1000',
      extended_price: '1000',
    },
  ],
}

function parseResult() {
  return {
    id: 'parse-result-1',
    asset_id: 'document-1',
    quotation_id: 'quote-1',
    status: 'confirmed',
    parser_name: 'devmind_standard_excel',
    parser_version: '1.0.0',
    content_hash: 'hash',
    normalized_json: candidate,
    source_totals_json: {
      subtotal_before_vat: '1000',
      vat_amount: '80',
      grand_total: '1080',
    },
    field_confidence_json: { quote_no: 1, items: 1 },
    validation_errors_json: [],
    validation_warnings_json: [],
    confidence: '1.0000',
  }
}

function quotationResponse(overrides = {}) {
  return {
    id: 'quote-1',
    quote_no: 'PARSE-DEMO-001',
    source_type: 'document_import',
    version_current: 1,
    product_line: 'BDR',
    project_name: 'Document Parsing Demo',
    currency: 'USD',
    payment_term_option: 'NET 30',
    payment_terms: 'NET 30',
    quote_date: '2026-07-22',
    expire_date: '2026-08-21',
    tax_label: 'VAT',
    vat_rate: '8.00',
    vat_amount: '80.00',
    software_subtotal: '1000.00',
    others_subtotal: '0.00',
    subtotal_before_vat: '1000.00',
    grand_total: '1080.00',
    remarks_disclaimer: '',
    issuer_company_name: 'OnePro Cloud Limited',
    issuer_contact_name: 'QA Sales',
    issuer_contact_email: 'sales@example.com',
    issuer_contact_title: 'Sales Manager',
    client_company: 'QA Customer',
    contact_person: 'QA Contact',
    email: 'customer@example.com',
    billing_company: 'QA Customer',
    billing_contact: 'QA Contact',
    billing_email: 'customer@example.com',
    created_by_email: 'admin@example.com',
    status: 'generated',
    created_at: '2026-07-22T09:00:00Z',
    updated_at: '2026-07-22T09:00:00Z',
    items: candidate.items,
    versions: [],
    ...overrides,
  }
}

test('synced Excel is automatically imported into the quote list', async ({
  page,
}) => {
  page.on('pageerror', (error) => {
    console.error(error.stack || error.message)
  })
  page.on('console', (message) => {
    if (message.type() === 'error') console.error(message.text())
  })
  let imported = false
  await page.route('**/api/v1/quotation/quotations?**', (route) => {
    route.fulfill({
      json: imported
        ? {
            total: 2,
            items: [
              quotationResponse(),
              quotationResponse({
                id: 'quote-material',
                quote_no: 'MATERIAL-001',
                project_name: 'Cloud DR VM inventory',
                client_company: 'Cloud DR VM inventory',
                contact_person: 'Not specified',
                email: 'unknown@oneprocloud.invalid',
                billing_contact: '',
                billing_email: '',
                vat_rate: '0.00',
                vat_amount: '0.00',
                software_subtotal: '0.00',
                subtotal_before_vat: '0.00',
                grand_total: '0.00',
                items: [],
              }),
            ],
          }
        : { items: [], total: 0 },
    })
  })
  await page.route('**/api/v1/quotation/feishu/sync-folder', (route) => {
    imported = true
    return route.fulfill({
      json: {
        created_count: 1,
        skipped_count: 0,
        parsed_count: 1,
        created_quotation_count: 1,
        errors: [],
        folders: [],
        file_locations: [],
        created_document_ids: ['document-1'],
        parsed_document_ids: ['document-1'],
        created_quotation_ids: ['quote-1'],
      },
    })
  })
  await page.route(
    '**/api/v1/quotation/documents?source=feishu**',
    (route) =>
      route.fulfill({
        json: [
          {
            id: 'document-1',
            quotation_id: null,
            doc_type: 'excel',
            file_name: 'Parsing Demo.xlsx',
            mime_type:
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            size_bytes: 4096,
            source: 'feishu',
            feishu_folder_path: [
              { token: 'root', name: 'Tower' },
              { token: 'sales', name: 'From QA' },
            ],
            parse_result_id: 'parse-result-1',
            parse_status: 'confirmed',
            parsed_quotation_id: 'quote-1',
            parsed_quote_no: 'PARSE-DEMO-001',
          },
        ],
      }),
  )
  await page.route(
    '**/api/v1/quotation/documents/document-1/parse',
    async (route) => {
      await route.fulfill({ json: parseResult() })
    },
  )

  await setupAuthenticatedSession(page)
  await page.goto('/quotation/list')

  await expect(page.getByText('Parsing Demo.xlsx')).toBeVisible()
  await expect(page.getByText(/Parsed|已解析/)).toBeVisible()
  await expect(page.getByText('PARSE-DEMO-001')).toBeVisible()
  await expect(page.getByText('Document Parsing Demo')).toBeVisible()
  const importedSearch = page.getByPlaceholder(
    'Search by file, folder, or quote number…',
  )
  await importedSearch.fill('PARSE-DEMO-001')
  await expect(page.getByText('Parsing Demo.xlsx')).toBeVisible()
  await importedSearch
    .locator('..')
    .getByRole('button', { name: 'Clear search' })
    .click()
  await expect(importedSearch).toHaveValue('')

  const importedQuoteRow = page
    .getByRole('row')
    .filter({ hasText: 'PARSE-DEMO-001' })
  await expect(importedQuoteRow.getByText('Parsed import')).toBeVisible()
  await expect(importedQuoteRow.getByText('QA Contact')).toBeVisible()
  await expect(importedQuoteRow.getByText('$1,080')).toBeVisible()
  await expect(importedQuoteRow.getByText('V1')).toHaveCount(0)
  await expect(importedQuoteRow.getByText('Generated')).toHaveCount(0)
  const quoteNumber = importedQuoteRow.getByTitle('PARSE-DEMO-001')
  await expect(quoteNumber).toBeVisible()
  await expect(quoteNumber).toHaveCSS('text-overflow', 'ellipsis')
  await expect(page.locator('main').first()).toHaveCSS('overflow-y', 'hidden')
  await expect(page.locator('#app-scroll-stage')).toHaveCSS(
    'overflow-y',
    'auto',
  )
  await expect(
    importedQuoteRow.getByTitle('View details'),
  ).toBeVisible()
  await expect(importedQuoteRow.getByTitle('Download')).toBeVisible()
  await expect(importedQuoteRow.getByTitle('Edit quote')).toHaveCount(0)
  await expect(importedQuoteRow.getByTitle('Upload to Feishu')).toHaveCount(0)
  await expect(importedQuoteRow.getByTitle('Delete quote')).toHaveCount(0)
  const materialRow = page.getByRole('row').filter({ hasText: 'MATERIAL-001' })
  await expect(materialRow.getByText('Not specified')).toHaveCount(0)
  await expect(materialRow.getByText('$0')).toHaveCount(0)
  await expect(materialRow.getByText('—', { exact: true })).toHaveCount(2)

  const quoteSearch = page.getByPlaceholder(
    'Quote no., project, company, contact…',
  )
  await quoteSearch.fill('MATERIAL-001')
  await expect(materialRow).toBeVisible()
  await expect(importedQuoteRow).toHaveCount(0)
  await quoteSearch
    .locator('..')
    .getByRole('button', { name: 'Clear search' })
    .click()
  await expect(quoteSearch).toHaveValue('')
  await expect(importedQuoteRow).toBeVisible()
  await expect(
    page.getByText(/Review parsed quotation|审核报价单解析结果/),
  ).toHaveCount(0)
  await page.screenshot({
    path: '/tmp/devmind-quotation-document-parsing.png',
    fullPage: true,
  })
})
