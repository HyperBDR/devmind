<script setup lang="ts">
import { computed } from 'vue'

import oneProLogo from '../../assets/onepro-logo.png'

export interface InvoicePreviewItem {
  id: string
  description: string
  quantity: number
  unitPrice: number
}

export interface InvoicePreviewData {
  invoiceNumber: string
  documentKind: string
  invoiceDate: string
  currency: string
  sellerName: string
  sellerAddress: string
  sellerWebsite: string
  sellerEmail: string
  customerName: string
  customerTaxId: string
  customerAddress: string
  customerContactPerson: string
  customerContactEmail: string
  customerContactPhone: string
  contactPerson: string
  contactEmail: string
  purchaseOrderNo: string
  paymentTerms: string
  additionalNotes: string
  remarks: string
  bankAccountName: string
  bankName: string
  bankAddress: string
  bankAccountNumber: string
  bankCode: string
  bankBranchCode: string
  bankSwiftCode: string
  remittanceInstruction: string
  signatoryName: string
  signatoryTitle: string
  signature: string
  items: InvoicePreviewItem[]
}

const props = defineProps<{
  invoice: InvoicePreviewData
}>()

const ITEMS_PER_PAGE = 7

const pages = computed(() => {
  const chunks: InvoicePreviewItem[][] = []
  for (let index = 0; index < props.invoice.items.length; index += ITEMS_PER_PAGE) {
    chunks.push(props.invoice.items.slice(index, index + ITEMS_PER_PAGE))
  }
  return chunks.length ? chunks : [[]]
})

const totalAmount = computed(() =>
  props.invoice.items.reduce(
    (total, item) => total + item.quantity * item.unitPrice,
    0,
  ),
)

function displayDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  return match ? `${match[3]}.${match[2]}.${match[1]}` : '—'
}

function currencyPrefix(currency: string): string {
  return {
    USD: '$',
    CNY: '¥',
    EUR: '€',
    GBP: '£',
    HKD: 'HK$',
    MYR: 'RM',
  }[currency] || currency
}

function formatAmount(value: number): string {
  return `${currencyPrefix(props.invoice.currency)} ${new Intl.NumberFormat(
    'en-US',
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
  ).format(Number.isFinite(value) ? value : 0)}`
}
</script>

<template>
  <div class="invoice-preview-pages" data-document-language="en">
    <article
      v-for="(pageItems, pageIndex) in pages"
      :key="pageIndex"
      class="commercial-invoice-page"
    >
      <template v-if="invoice.documentKind === 'delivery_note'">
        <header class="invoice-document-header">
          <img :src="oneProLogo" alt="OnePro" class="invoice-logo" />
          <div class="invoice-document-title">
            <strong>{{ invoice.sellerName || 'OnePro Cloud Limited' }}</strong>
            <h2>Delivery Note</h2>
          </div>
        </header>

        <section class="invoice-company-row">
          <div class="invoice-seller-copy">
            <strong>{{ invoice.sellerName || '—' }}</strong>
            <p v-if="invoice.sellerAddress">{{ invoice.sellerAddress }}</p>
            <p v-if="invoice.sellerWebsite" class="invoice-underlined">
              {{ invoice.sellerWebsite }}
            </p>
            <p v-if="invoice.sellerEmail" class="invoice-underlined">
              {{ invoice.sellerEmail }}
            </p>
          </div>
          <dl class="invoice-identifiers">
            <dt>Date:</dt>
            <dd>{{ displayDate(invoice.invoiceDate) }}</dd>
            <dt>Delivery Note Number:</dt>
            <dd>{{ invoice.invoiceNumber || '—' }}</dd>
          </dl>
        </section>

        <section class="invoice-bill-to">
          <h3>Recipient:</h3>
          <dl>
            <dt>Company:</dt>
            <dd>{{ invoice.customerName || '—' }}</dd>
            <template v-if="invoice.customerContactPerson">
              <dt>Name:</dt>
              <dd>{{ invoice.customerContactPerson }}</dd>
            </template>
            <template v-if="invoice.customerAddress">
              <dt>Address:</dt>
              <dd>{{ invoice.customerAddress }}</dd>
            </template>
            <template v-if="invoice.customerContactEmail">
              <dt>Email:</dt>
              <dd>{{ invoice.customerContactEmail }}</dd>
            </template>
          </dl>
        </section>

        <table class="invoice-contact-table delivery-note-contact-table">
          <thead>
            <tr>
              <th>Contact Person</th>
              <th>Email</th>
              <th>PO#</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{{ invoice.contactPerson || '—' }}</td>
              <td>{{ invoice.contactEmail || '—' }}</td>
              <td>{{ invoice.purchaseOrderNo || '—' }}</td>
            </tr>
          </tbody>
        </table>

        <div class="invoice-section-rule" />

        <table class="invoice-items-table delivery-note-items-table">
          <colgroup>
            <col class="invoice-item-number" />
            <col class="invoice-item-description" />
            <col class="invoice-item-quantity" />
            <col class="delivery-note-date" />
          </colgroup>
          <thead>
            <tr>
              <th>Item</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Date of Delivery</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, itemIndex) in pageItems" :key="item.id">
              <td>{{ pageIndex * ITEMS_PER_PAGE + itemIndex + 1 }}</td>
              <td>{{ item.description || '—' }}</td>
              <td>{{ item.quantity }}</td>
              <td>{{ displayDate(invoice.invoiceDate) }}</td>
            </tr>
            <tr v-if="pageItems.length === 0">
              <td>1</td>
              <td>—</td>
              <td>—</td>
              <td>{{ displayDate(invoice.invoiceDate) }}</td>
            </tr>
          </tbody>
        </table>

        <section class="invoice-notes-block delivery-note-remarks">
          <h3>Remarks:</h3>
          <p>{{ invoice.remarks || invoice.additionalNotes || '—' }}</p>
        </section>
      </template>
      <template v-else>
      <header class="invoice-document-header">
        <img :src="oneProLogo" alt="OnePro" class="invoice-logo" />
        <div class="invoice-document-title">
          <strong>{{ invoice.sellerName || 'OnePro Cloud Limited' }}</strong>
          <h2 v-if="invoice.documentKind === 'proforma_invoice'">
            Proforma Invoice
          </h2>
          <h2 v-else>Commercial Invoice</h2>
        </div>
      </header>

      <section class="invoice-company-row">
        <div class="invoice-seller-copy">
          <strong>{{ invoice.sellerName || '—' }}</strong>
          <p v-if="invoice.sellerAddress">{{ invoice.sellerAddress }}</p>
          <p v-if="invoice.sellerWebsite" class="invoice-underlined">
            {{ invoice.sellerWebsite }}
          </p>
          <p v-if="invoice.sellerEmail" class="invoice-underlined">
            {{ invoice.sellerEmail }}
          </p>
        </div>
        <dl class="invoice-identifiers">
          <dt>Date:</dt>
          <dd>{{ displayDate(invoice.invoiceDate) }}</dd>
          <dt v-if="invoice.documentKind === 'proforma_invoice'">
            Proforma Invoice Number:
          </dt>
          <dt v-else>Invoice Number:</dt>
          <dd>{{ invoice.invoiceNumber || '—' }}</dd>
        </dl>
      </section>

      <section class="invoice-bill-to">
        <h3>Bill to:</h3>
        <dl>
          <dt>Company:</dt>
          <dd>{{ invoice.customerName || '—' }}</dd>
          <template v-if="invoice.customerContactPerson">
            <dt>Name:</dt>
            <dd>{{ invoice.customerContactPerson }}</dd>
          </template>
          <template v-if="invoice.customerTaxId">
            <dt>VAT NO:</dt>
            <dd>{{ invoice.customerTaxId }}</dd>
          </template>
          <template v-if="invoice.customerAddress">
            <dt>Address:</dt>
            <dd>{{ invoice.customerAddress }}</dd>
          </template>
          <template v-if="invoice.customerContactEmail">
            <dt>Email:</dt>
            <dd>{{ invoice.customerContactEmail }}</dd>
          </template>
          <template v-if="invoice.customerContactPhone">
            <dt>Contact:</dt>
            <dd>{{ invoice.customerContactPhone }}</dd>
          </template>
        </dl>
      </section>

      <table class="invoice-contact-table">
        <thead>
          <tr>
            <th>Contact Person</th>
            <th>Email</th>
            <th>PO#</th>
            <th>Currency</th>
            <th>Payment Term</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{{ invoice.contactPerson || '—' }}</td>
            <td>{{ invoice.contactEmail || '—' }}</td>
            <td>{{ invoice.purchaseOrderNo || '—' }}</td>
            <td>{{ invoice.currency }}</td>
            <td>{{ invoice.paymentTerms || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="invoice-section-rule" />

      <table class="invoice-items-table">
        <colgroup>
          <col class="invoice-item-number" />
          <col class="invoice-item-description" />
          <col class="invoice-item-quantity" />
          <col class="invoice-item-price" />
          <col class="invoice-item-extended" />
        </colgroup>
        <thead>
          <tr>
            <th>Item</th>
            <th>Description</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Extended Price</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, itemIndex) in pageItems" :key="item.id">
            <td>{{ pageIndex * ITEMS_PER_PAGE + itemIndex + 1 }}</td>
            <td>{{ item.description || '—' }}</td>
            <td>{{ item.quantity }}</td>
            <td>{{ formatAmount(item.unitPrice) }}</td>
            <td>{{ formatAmount(item.quantity * item.unitPrice) }}</td>
          </tr>
          <tr v-if="pageItems.length === 0">
            <td>1</td>
            <td>—</td>
            <td>—</td>
            <td>—</td>
            <td>—</td>
          </tr>
        </tbody>
      </table>

      <template v-if="pageIndex === pages.length - 1">
        <div class="invoice-total-row">
          <strong>Total Amount:</strong>
          <strong>{{ formatAmount(totalAmount) }}</strong>
        </div>

        <section class="invoice-notes-block">
          <h3>Additional Notes &amp; Disclaimers:</h3>
          <p>{{ invoice.additionalNotes || '—' }}</p>
        </section>

        <section class="invoice-footer">
          <div class="invoice-bank-details">
            <h3>Remarks:</h3>
            <p v-if="invoice.remarks">{{ invoice.remarks }}</p>
            <dl>
              <dt>Account Name:</dt>
              <dd>{{ invoice.bankAccountName || '—' }}</dd>
              <dt>Bank Name:</dt>
              <dd>{{ invoice.bankName || '—' }}</dd>
              <dt>Bank Address:</dt>
              <dd>{{ invoice.bankAddress || '—' }}</dd>
              <dt>Account Number:</dt>
              <dd>{{ invoice.bankAccountNumber || '—' }}</dd>
              <dt>Bank Code:</dt>
              <dd>{{ invoice.bankCode || '—' }}</dd>
              <dt>Branch Code:</dt>
              <dd>{{ invoice.bankBranchCode || '—' }}</dd>
              <dt>SWIFT CODE:</dt>
              <dd>{{ invoice.bankSwiftCode || '—' }}</dd>
            </dl>
            <p class="invoice-remittance">
              {{ invoice.remittanceInstruction || '—' }}
            </p>
          </div>

          <div class="invoice-signature-block">
            <strong>{{ invoice.sellerName || 'OnePro Cloud Limited' }}</strong>
            <div class="invoice-signature-image-wrap">
              <img
                v-if="invoice.signature"
                :src="invoice.signature"
                alt="Authorized signature"
              />
            </div>
            <div class="invoice-signature-line" />
            <dl>
              <dt>Name:</dt>
              <dd>{{ invoice.signatoryName || '—' }}</dd>
              <dt>Title:</dt>
              <dd>{{ invoice.signatoryTitle || '—' }}</dd>
              <dt>Date:</dt>
              <dd>{{ displayDate(invoice.invoiceDate) }}</dd>
            </dl>
          </div>
        </section>
      </template>

      <p v-else class="invoice-continued">
        Invoice items continued on next page
      </p>
      <p v-if="pages.length > 1" class="invoice-page-number">
        Page {{ pageIndex + 1 }} / {{ pages.length }}
      </p>
      </template>
    </article>
  </div>
</template>

<style scoped>
.invoice-preview-pages {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.commercial-invoice-page {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  min-width: 620px;
  max-width: 210mm;
  aspect-ratio: 210 / 297;
  padding: 6.5% 7% 5.5%;
  background: #fff;
  color: #161616;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10.5px;
  line-height: 1.35;
  box-shadow: 0 2px 12px rgb(15 23 42 / 12%);
}

.invoice-document-header {
  display: grid;
  grid-template-columns: 34% 1fr 22%;
  align-items: center;
  min-height: 70px;
}

.invoice-logo {
  width: 145px;
  height: auto;
}

.invoice-document-title {
  grid-column: 2;
  text-align: center;
}

.invoice-document-title strong {
  display: block;
  margin-bottom: 9px;
  font-size: 19px;
  font-weight: 500;
}

.invoice-document-title h2 {
  display: inline-block;
  margin: 0;
  border-bottom: 1px solid #111;
  font-size: 17px;
  font-weight: 500;
}

.invoice-company-row {
  display: grid;
  grid-template-columns: 1fr 245px;
  gap: 40px;
  margin-top: 34px;
}

.invoice-seller-copy p {
  margin: 1px 0;
  white-space: pre-line;
}

.invoice-underlined {
  text-decoration: underline;
}

.invoice-identifiers {
  display: grid;
  grid-template-columns: 105px 1fr;
  gap: 14px 8px;
  align-content: start;
  margin: 0;
}

.invoice-identifiers dt {
  font-weight: 700;
  text-align: right;
}

.invoice-identifiers dd {
  margin: 0;
  border-bottom: 1px solid #777;
  text-align: center;
}

.invoice-bill-to {
  width: 58%;
  min-height: 92px;
  margin-top: 34px;
  border: 1px solid #777;
}

.invoice-bill-to h3,
.invoice-notes-block h3 {
  margin: 0;
  padding: 2px 6px;
  background: #8a8a8a;
  color: #fff;
  font-size: 10px;
  font-weight: 500;
  text-align: center;
}

.invoice-bill-to dl,
.invoice-bank-details dl,
.invoice-signature-block dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 1px 7px;
  margin: 5px 6px;
}

.invoice-bill-to dt,
.invoice-bank-details dt,
.invoice-signature-block dt {
  font-weight: 500;
}

.invoice-bill-to dd,
.invoice-bank-details dd,
.invoice-signature-block dd {
  margin: 0;
  white-space: pre-line;
}

.invoice-contact-table,
.invoice-items-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.invoice-contact-table {
  margin-top: 27px;
}

.invoice-contact-table th,
.invoice-contact-table td,
.invoice-items-table th,
.invoice-items-table td {
  border: 1px solid #777;
  padding: 3px 5px;
}

.invoice-contact-table th,
.invoice-items-table th {
  background: #8a8a8a;
  color: #fff;
  font-weight: 500;
  text-align: center;
}

.invoice-contact-table td {
  overflow-wrap: anywhere;
  font-size: 9px;
  text-align: center;
}

.invoice-section-rule {
  height: 2px;
  margin: 34px 0 29px;
  background: #555;
}

.invoice-item-number { width: 7%; }
.invoice-item-description { width: 58%; }
.invoice-item-quantity { width: 7%; }
.invoice-item-price { width: 13%; }
.invoice-item-extended { width: 15%; }
.delivery-note-date { width: 20%; }

.invoice-items-table td:first-child,
.invoice-items-table td:nth-child(3) {
  text-align: center;
}

.invoice-items-table td:nth-child(4),
.invoice-items-table td:nth-child(5) {
  text-align: right;
}

.invoice-items-table td:nth-child(2) {
  white-space: pre-line;
}

.delivery-note-items-table td:nth-child(4) {
  text-align: center;
  white-space: nowrap;
}

.delivery-note-remarks {
  margin-top: 34px;
}

.invoice-total-row {
  display: grid;
  grid-template-columns: 1fr 165px;
  gap: 10px;
  margin-top: 10px;
  text-align: right;
}

.invoice-total-row strong:last-child {
  border-bottom: 1px solid #333;
}

.invoice-notes-block {
  min-height: 60px;
  margin-top: 16px;
  border: 1px solid #777;
}

.invoice-notes-block h3 {
  background: transparent;
  color: #111;
  font-style: italic;
  font-weight: 700;
  text-align: left;
}

.invoice-notes-block p {
  margin: 2px 6px;
  white-space: pre-line;
}

.invoice-footer {
  display: grid;
  grid-template-columns: 64% 31%;
  gap: 5%;
  margin-top: 25px;
}

.invoice-bank-details h3 {
  margin: 0 0 7px;
  font-size: 10px;
}

.invoice-bank-details dl {
  margin: 0;
  padding: 4px;
  border: 1px solid #777;
}

.invoice-remittance {
  margin: 3px 0 0;
  font-size: 9px;
  font-style: italic;
  white-space: pre-line;
}

.invoice-signature-block {
  padding-top: 22px;
  text-align: center;
}

.invoice-signature-image-wrap {
  display: flex;
  height: 55px;
  align-items: end;
  justify-content: center;
}

.invoice-signature-image-wrap img {
  max-width: 150px;
  max-height: 55px;
  object-fit: contain;
}

.invoice-signature-line {
  border-bottom: 1px solid #555;
}

.invoice-signature-block dl {
  margin: 4px 0 0;
  text-align: left;
}

.invoice-continued,
.invoice-page-number {
  color: #555;
  font-size: 9px;
  text-align: center;
}

.invoice-continued {
  margin-top: 18px;
  font-style: italic;
}

.invoice-page-number {
  position: absolute;
  right: 7%;
  bottom: 4%;
  margin: 0;
}

@media print {
  .commercial-invoice-page {
    break-after: page;
    box-shadow: none;
  }
}
</style>
