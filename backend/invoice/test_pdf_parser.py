from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from invoice.parsing.pdf_parser import parse_invoice_pdf


class InvoicePdfParserTests(SimpleTestCase):
    def test_sparse_pdf_text_is_supplemented_with_shared_ocr(self):
        embedded = (
            "Withholding Tax : OnePro Cloud Limited\n"
            "INVOICE PO WHT\n"
            "INV.BDR030325 VPOI68020003 No.0719/ro/002867\n"
        )
        ocr_text = (
            "Amount of tax withheld and date of tax payment\n"
            "2,594.59 Baht\nMay 13, 2025\n"
        )
        with patch(
            "invoice.parsing.pdf_parser.extract_pdf_text",
            return_value=embedded,
        ), patch(
            "invoice.parsing.pdf_parser.extract_pdf_text_with_ocr",
            return_value=ocr_text,
        ) as ocr:
            parsed = parse_invoice_pdf(Path("sparse.pdf"))

        ocr.assert_called_once_with(Path("sparse.pdf"), dpi=300)
        self.assertEqual(parsed.invoice.invoice_no, "INV.BDR030325")
        self.assertEqual(parsed.invoice.invoice_date, date(2025, 5, 13))
        self.assertEqual(parsed.invoice.currency, "THB")
        self.assertEqual(parsed.invoice.total_amount, Decimal("2594.59"))

    def test_scanned_pdf_uses_shared_ocr_fallback(self):
        with patch(
            "invoice.parsing.pdf_parser.extract_pdf_text",
            return_value="",
        ), patch(
            "invoice.parsing.pdf_parser.extract_pdf_text_with_ocr",
            return_value=(
                "Invoice Number: INV-OCR\n"
                "Date: 08.09.2026\n"
                "Company: OCR Customer"
            ),
        ) as ocr:
            parsed = parse_invoice_pdf(Path("scanned.pdf"))

        ocr.assert_called_once_with(Path("scanned.pdf"), dpi=300)
        self.assertEqual(parsed.invoice.invoice_no, "INV-OCR")
        self.assertEqual(parsed.invoice.customer_name, "OCR Customer")

    def test_extracts_invoice_dimensions_and_line_items(self):
        text = """Invoice No: INV-100
Invoice Date: 2026-09-04
Seller: OnePro Cloud
Customer: Acme Ltd
Region: APAC
Currency: USD
Tax Rate: 10%
Subtotal: 100.00
Tax Amount: 10.00
Grand Total: 110.00
Item Description Qty Unit Price Amount
1 Cloud migration 2 50.00 100.00
"""

        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("invoice.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "INV-100")
        self.assertEqual(parsed.invoice.customer_name, "Acme Ltd")
        self.assertEqual(parsed.invoice.total_amount, 110)
        self.assertEqual(
            parsed.invoice.items[0].product_name,
            "Cloud migration",
        )

    def test_missing_lines_are_reported_for_review(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value="Invoice No: INV-101\nCustomer: Acme Ltd",
        ):
            parsed = parse_invoice_pdf(Path("invoice.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "INV-101")
        self.assertEqual(parsed.invoice.items, [])
        self.assertEqual(
            parsed.validation_warnings[0]["code"],
            "items_not_detected",
        )

    def test_parser_reads_the_issued_commercial_invoice_layout(self):
        text = """
OnePro Cloud Limited
Commercial Invoice

OnePro Cloud Limited             Date: 08.09.2026
Invoice Number: INV-202609-0001

Bill to:
Company: Automatic Numbering QA Ltd.

Item Description Qty Price Extended Price
1 Annual platform subscription 1 $ 5,000.00 $ 5,000.00

Total Amount: $ 5,000.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("invoice.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "INV-202609-0001")
        self.assertEqual(
            parsed.invoice.invoice_date.isoformat(),
            "2026-09-08",
        )
        self.assertEqual(
            parsed.invoice.customer_name,
            "Automatic Numbering QA Ltd.",
        )
        self.assertEqual(len(parsed.invoice.items), 1)
        self.assertEqual(
            parsed.invoice.items[0].description,
            "Annual platform subscription",
        )
        self.assertEqual(parsed.invoice.items[0].quantity, 1)
        self.assertEqual(parsed.invoice.items[0].unit_price, 5000)
        self.assertEqual(parsed.invoice.total_amount, 5000)

    def test_parser_reads_the_commercial_invoice_footer(self):
        text = """Commercial Invoice
Invoice Number: Motion010926
Date: 01.09.2026
Company: Ai-T Consulting Services (Pty) Ltd
Total Amount: $ 2,500.00
Remarks:
Account Name: OnePro Cloud Limited
Bank Name: DBS Bank Limited, Hong Kong Branch
Bank Address: 18th Floor, The Center, 99 Queen's Road Central
Account Number: 20000723088
Bank Code: 185
Branch Code: 927
SWIFT CODE: DBSSHKHH
Please use the Invoice number as a reference and email remittance advice to ecosys@oneprocloud.com
Name : Natalie Chan
Title : Marketing & Operations Senior Manager
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("invoice.pdf"))

        invoice = parsed.invoice
        self.assertEqual(invoice.bank_account_name, "OnePro Cloud Limited")
        self.assertEqual(
            invoice.bank_name,
            "DBS Bank Limited, Hong Kong Branch",
        )
        self.assertEqual(
            invoice.bank_address,
            "18th Floor, The Center, 99 Queen's Road Central",
        )
        self.assertEqual(invoice.bank_account_number, "20000723088")
        self.assertEqual(invoice.bank_code, "185")
        self.assertEqual(invoice.bank_branch_code, "927")
        self.assertEqual(invoice.bank_swift_code, "DBSSHKHH")
        self.assertEqual(
            invoice.remittance_instruction,
            "Please use the Invoice number as a reference and email "
            "remittance advice to ecosys@oneprocloud.com",
        )
        self.assertEqual(invoice.signatory_name, "Natalie Chan")
        self.assertEqual(
            invoice.signatory_title,
            "Marketing & Operations Senior Manager",
        )

    def test_parser_keeps_proforma_notes_and_beneficiary(self):
        text = """Proforma Invoice
Proforma Invoice Number: 051225_BoG_A-B
Additional Notes & Disclaimers:
- VAT not applicable as per Hong Kong regulations.

- Quotation# PS101125_R1
Remarks:
Bank Name: DBS Bank Limited, Hong Kong Branch
Bank Account Beneficiary: OnePro Cloud Limited
Bank Code: 185
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("proforma-footer.pdf"))

        invoice = parsed.invoice
        self.assertEqual(
            invoice.additional_notes,
            "VAT not applicable as per Hong Kong regulations.\n"
            "Quotation# PS101125_R1",
        )
        self.assertEqual(
            invoice.bank_account_name,
            "OnePro Cloud Limited",
        )

    def test_parser_merges_wrapped_item_description(self):
        text = """Invoice
Item Description Qty Price Extended Price
  Setup
    Configuración de Ambiente de Disaster Recovery
    Setup Seguridad Infraestructura Ambiente Disaster Recovery
    Prueba DR (Evento)
    Setup SOC
1                                      1 $ 324,000.00 $324,000.00
  1st Year
  Ongoing SOC
  Servicio de Continuidad
  Soporte NOC
Total Amount: $324,000.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("wrapped-item.pdf"))

        self.assertEqual(
            parsed.invoice.items[0].description,
            "Setup\nConfiguración de Ambiente de Disaster Recovery\n"
            "Setup Seguridad Infraestructura Ambiente Disaster Recovery\n"
            "Prueba DR (Evento)\nSetup SOC\n1st Year\nOngoing SOC\n"
            "Servicio de Continuidad\nSoporte NOC",
        )
        self.assertEqual(parsed.invoice.items[0].product_name, "Setup")

    def test_parser_reads_two_column_date_and_number_labels(self):
        text = """OnePro Cloud Limited        Date:      21.08.2026
Invoice Number:     BDR210826
Company : Ai-T Consulting Services (Pty) Ltd
Total Amount: $10,180.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("two-column.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "BDR210826")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2026-08-21")

    def test_parser_reads_payment_receipt_layout(self):
        text = """Receipt

Invoice number BFYXEJBS-0001
Date paid       July 30, 2025

OnePro Cloud Limited                                       Bill to
九龍                                          Husamettin Batur
UNIT 701A, 7/F, RAILWAY PLAZA  Necip Fazil Sok. Ilica Sok. No:13 D:1

$35.00 paid on July 30, 2025

Description  Qty  Unit price  Amount
HyperBDR Monthly Subscription                    1       $35.00      $35.00

Subtotal                                          $35.00
Total                                             $35.00
Amount paid                                      $35.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("receipt.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "BFYXEJBS-0001")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-07-30")
        self.assertEqual(parsed.invoice.customer_name, "Husamettin Batur")
        self.assertEqual(parsed.invoice.total_amount, 35)
        self.assertEqual(parsed.invoice.items[0].quantity, 1)

    def test_parser_reads_stripe_invoice_dates_currency_and_amount(self):
        text = """Invoice

Invoice number 26484088-0002
Date of issue   May 23, 2025
Date due      May 23, 2025

OnePro Cloud Limited                                       Bill to
九龍                                          Ghaleb Alhaddad
UNIT 701A, 7/F, RAILWAY PLAZA                 Riyadh
39 CHATHAM ROAD SOUTH                         Saudi Arabia
CS@oneprocloud.com                            galhaddad@btc.com.sa

$105.00 USD due May 23, 2025

Description  Qty  Unit price  Amount
HyperBDR Monthly Subscription                    3       $35.00      $105.00

Subtotal                                          $105.00
Total                                             $105.00
Amount due                                        $105.00 USD
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("stripe-invoice.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "26484088-0002")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-05-23")
        self.assertEqual(parsed.invoice.due_date.isoformat(), "2025-05-23")
        self.assertEqual(parsed.invoice.customer_name, "Ghaleb Alhaddad")
        self.assertEqual(
            parsed.invoice.customer_contact_person,
            "Ghaleb Alhaddad",
        )
        self.assertEqual(
            parsed.invoice.customer_contact_email,
            "galhaddad@btc.com.sa",
        )
        self.assertEqual(parsed.invoice.contact_person, "")
        self.assertEqual(parsed.invoice.contact_email, "")
        self.assertEqual(
            parsed.invoice.customer_address,
            "Riyadh, Saudi Arabia",
        )
        self.assertEqual(parsed.invoice.currency, "USD")
        self.assertEqual(parsed.invoice.total_amount, 105)
        self.assertEqual(parsed.invoice.items[0].quantity, 3)
        self.assertEqual(parsed.invoice.items[0].unit_price, 35)

    def test_parser_reads_legacy_hkd_commercial_invoice(self):
        text = """OnePro Cloud Limited

Deliver To: OnePro Cloud Co., Limited                 Commercial Invoice
PO No. : BMS_MAR2025          Date (DD/MM/YY): 07.03.25
Bill To: OnePro Cloud Co., Limited  Due Date (DD/MM/YY): 09.04.25
Invoice No.: BMS_MAR2025                              Currency: HKD

Item# CRU Part Number Description Qty UOM Unit Price Amount
1 BMS Business Management Service - MAR 2025 1 EA HK$220,000.00 HK$220,000.00

Disclaimer: standard terms                                TOTAL
Seller's only obligation shall be to replace defective products.
HK$220,000.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("legacy-hkd.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "BMS_MAR2025")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-03-07")
        self.assertEqual(parsed.invoice.due_date.isoformat(), "2025-04-09")
        self.assertEqual(
            parsed.invoice.customer_name,
            "OnePro Cloud Co., Limited",
        )
        self.assertEqual(parsed.invoice.currency, "HKD")
        self.assertEqual(parsed.invoice.purchase_order_no, "BMS_MAR2025")
        self.assertEqual(parsed.invoice.total_amount, 220000)
        self.assertEqual(parsed.invoice.contact_person, "")
        self.assertEqual(parsed.invoice.customer_address, "")
        self.assertEqual(parsed.invoice.items[0].quantity, 1)
        self.assertEqual(parsed.invoice.items[0].unit_price, 220000)

    def test_parser_reads_malaysia_currency_and_total(self):
        text = """OnePro Cloud Limited
Commercial Invoice

OnePro Cloud Limited                              Date: 04.12.2025
Invoice Number: BDR041225

Bill to:
Company : TT DOTCOM SDN BHD (TIME)
Name : Md Fadhil Bin Md Rashid
Address : No. 14, Jalan Majistret U1/26
40150 Shah Alam, Selangor Darul Ehsan.
Email : md.fadhil@time.com.my

Contact Person Email PO# Currency Payment Term
Natalie ecosys@oneprocloud.com 4500106655 MYR NET45

Item Description Qty Price Extended Price
1 HyperBDR Backup & DR License @ RM37.04 12 MYR 37.04 MYR 444.48

Total Amount: MYR 444.48
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("malaysia.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "BDR041225")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-12-04")
        self.assertEqual(parsed.invoice.currency, "MYR")
        self.assertEqual(parsed.invoice.purchase_order_no, "4500106655")
        self.assertEqual(parsed.invoice.payment_terms, "NET45")
        self.assertEqual(parsed.invoice.payment_terms, "NET45")
        self.assertEqual(parsed.invoice.total_amount, Decimal("444.48"))
        self.assertEqual(
            parsed.invoice.customer_name,
            "TT DOTCOM SDN BHD (TIME)",
        )
        self.assertEqual(parsed.invoice.contact_person, "Natalie")
        self.assertEqual(
            parsed.invoice.contact_email,
            "ecosys@oneprocloud.com",
        )
        self.assertEqual(
            parsed.invoice.customer_contact_person,
            "Md Fadhil Bin Md Rashid",
        )
        self.assertEqual(
            parsed.invoice.customer_contact_email,
            "md.fadhil@time.com.my",
        )
        self.assertEqual(parsed.invoice.signatory_name, "")
        self.assertEqual(parsed.invoice.signatory_title, "")
        self.assertEqual(
            parsed.invoice.customer_address,
            "No. 14, Jalan Majistret U1/26, "
            "40150 Shah Alam, Selangor Darul Ehsan.",
        )
        self.assertEqual(parsed.invoice.items[0].unit_price, Decimal("37.04"))
        self.assertEqual(
            parsed.invoice.items[0].total_amount,
            Decimal("444.48"),
        )

    def test_parser_cleans_ocr_contact_punctuation(self):
        text = """Commercial Invoice
Invoice Number: BDR190625
Date: 19.06.2025

Bill to:
Company : Ai-T Consulting Services (Pty) Ltd
Name : Vandana
Address : Unit 35 Polo Fields
Contact# : 0027740343138
Email : info@aitcs.co.za

Contact Person Email PO# Currency Payment Term
; LUCY ecosys@oneprocloud.com 20250609001 USD Due Now

Item Description Qty Price Extended Price
1 HyperBDR License 5 USD 10.00 USD 600.00
Total Amount: USD 600.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("ocr-contacts.pdf"))

        invoice = parsed.invoice
        self.assertEqual(invoice.contact_person, "LUCY")
        self.assertEqual(invoice.contact_email, "ecosys@oneprocloud.com")
        self.assertEqual(invoice.customer_contact_person, "Vandana")
        self.assertEqual(invoice.customer_contact_email, "info@aitcs.co.za")
        self.assertEqual(invoice.customer_contact_phone, "0027740343138")

    def test_parser_recovers_roles_when_ocr_drops_bill_to_heading(self):
        text = """a
COnerrsa
OnePro Cloud Limited
Commercial Invoice
OnePro Cloud Limited Date: 19.06.2025
Invoice Number: BDR190625
Company : Ai-T Consulting Services (Pty) Ltd
Name: Vandana
Address: Unit 35 polo fields cullinan close morningside sandton 2057
| Contact#: 0027740343138
| Email :_info@aitcs.co.za iadiecacabe oa
Cantact Person Email POF Currency. Payment Term
if LUCY ecosys@onenrocloud com __ 20250609001 _ UsD | __DueNow
Total Amount: $ 600.00
Pleose use the Invoice number os a reference and email remittance advice to
ecosys@oneprocioud.com
OnePro Cloud Limited
Name : LUCY 4
Title : Finance
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("real-ocr-contacts.pdf"))

        invoice = parsed.invoice
        self.assertEqual(invoice.customer_contact_person, "Vandana")
        self.assertEqual(invoice.customer_contact_email, "info@aitcs.co.za")
        self.assertEqual(invoice.customer_contact_phone, "0027740343138")
        self.assertEqual(invoice.contact_person, "LUCY")
        self.assertEqual(invoice.contact_email, "ecosys@oneprocloud.com")

    def test_parser_does_not_treat_vat_number_as_tax_rate(self):
        text = """Commercial Invoice
Invoice Number: VAT-NO-1
Date: 23.10.2025
Company: Customer Ltd
VAT NO: 4090263635
Total Amount: USD 10.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("vat-number.pdf"))

        self.assertEqual(parsed.invoice.tax_rate, Decimal("0"))

    def test_parser_supports_contact_name_and_email_on_separate_lines(self):
        text = """Commercial Invoice
Invoice Number: BDR190625
Date: 19.06.2025
Bill to:
Company: Customer Ltd
Name
Vandana
Email
info@example.com
Contact Person Email PO# Currency Payment Term
LUCY
ecosys@oneprocloud.com
PO-1 USD Due Now
Total Amount: USD 10.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("vertical-contacts.pdf"))

        invoice = parsed.invoice
        self.assertEqual(invoice.customer_contact_person, "Vandana")
        self.assertEqual(invoice.customer_contact_email, "info@example.com")
        self.assertEqual(invoice.contact_person, "LUCY")
        self.assertEqual(invoice.contact_email, "ecosys@oneprocloud.com")

    def test_parser_keeps_customer_and_footer_fields_in_their_sections(self):
        text = """Commercial Invoice
Seller: OnePro Cloud Limited
Seller Tax ID: HK-SELLER-1
Invoice Number: INV-SECTION-1
Date: 10.09.2026

Bill to:
Company: Acme Limited
Customer Tax ID: MY-CUSTOMER-2
Name: Alice Buyer
Address: 1 Customer Road
Email: alice@example.com
Bank Name: Customer Bank That Must Not Leak
Account Number: 999999

Contact Person Email PO# Currency Payment Term
Natalie ecosys@oneprocloud.com PO-100 USD NET30

Item Description Qty Price Extended Price
1 Platform subscription 2 USD 50.00 USD 100.00

Notes:
Pay before delivery.
Additional Notes & Disclaimers:
Subject to contract.
Remarks:
Account Name: OnePro Cloud Limited
Bank Name: DBS Bank
Bank Address: 18 Bank Road
Account Number: 123456
Bank Code: 185
Branch Code: 927
SWIFT CODE: DBSSHKHH
Name: Carol Signer
Title: Finance Director
Total Amount: USD 100.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("sectioned-invoice.pdf"))

        invoice = parsed.invoice
        self.assertEqual(invoice.seller_name, "OnePro Cloud Limited")
        self.assertEqual(invoice.seller_tax_id, "HK-SELLER-1")
        self.assertEqual(invoice.customer_name, "Acme Limited")
        self.assertEqual(invoice.customer_tax_id, "MY-CUSTOMER-2")
        self.assertEqual(invoice.customer_contact_person, "Alice Buyer")
        self.assertEqual(invoice.customer_contact_email, "alice@example.com")
        self.assertEqual(invoice.customer_address, "1 Customer Road")
        self.assertEqual(invoice.contact_person, "Natalie")
        self.assertEqual(invoice.contact_email, "ecosys@oneprocloud.com")
        self.assertEqual(invoice.purchase_order_no, "PO-100")
        self.assertEqual(invoice.currency, "USD")
        self.assertEqual(invoice.payment_terms, "NET30")
        self.assertEqual(invoice.notes, "Pay before delivery.")
        self.assertEqual(invoice.additional_notes, "Subject to contract.")
        self.assertEqual(invoice.bank_account_name, "OnePro Cloud Limited")
        self.assertEqual(invoice.bank_name, "DBS Bank")
        self.assertEqual(invoice.bank_address, "18 Bank Road")
        self.assertEqual(invoice.signatory_name, "Carol Signer")
        self.assertEqual(invoice.signatory_title, "Finance Director")

    def test_footer_name_does_not_fill_missing_customer_contact(self):
        text = """Commercial Invoice
Invoice Number: INV-NO-BILL-TO
Date: 10.09.2026
Customer: Acme Limited
Total Amount: USD 100.00
Name: Carol Signer
Title: Finance Director
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("no-bill-to.pdf"))

        self.assertEqual(parsed.invoice.customer_name, "Acme Limited")
        self.assertEqual(parsed.invoice.customer_contact_person, "")
        self.assertEqual(parsed.invoice.customer_contact_email, "")
        self.assertEqual(parsed.invoice.signatory_name, "Carol Signer")

    def test_parser_uses_explicit_currency_for_multi_currency_total(self):
        text = """Commercial Invoice
Date: 26.01.2026
Invoice Number: BDR260126
Company: CREDENCE (MALAYSIA) SDN BHD
Contact Person Email PO# Currency Payment Term
Natalie ecosys@oneprocloud.com 4800428107 MYR CIA
Grand Total (USD) USD 5,898.58
Grand Total (MYR): MYR 25,658.83
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("multi-currency.pdf"))

        self.assertEqual(parsed.invoice.currency, "MYR")
        self.assertEqual(parsed.invoice.total_amount, Decimal("25658.83"))

    def test_parser_normalizes_spaced_net_payment_terms(self):
        text = """Commercial Invoice
Date: 26.01.2026
Invoice Number: BDR260126
Contact Person Email PO# Currency Payment Term
Natalie ecosys@oneprocloud.com 4800428107 USD NET 45
Grand Total: USD 100.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("spaced-payment-term.pdf"))

        self.assertEqual(parsed.invoice.payment_terms, "NET45")

    def test_parser_reads_chinese_stripe_invoice_fields(self):
        text = """账单

账单编号Q3YGPVNT-0001
发出日期2025年5月29日
到期日  2025年5月29日

OnePro Cloud Limited              收票人
九龍                               李坤
UNIT 701A                          100086
39 CHATHAM ROAD SOUTH             北京市北京
CS@oneprocloud.com                user@example.cn

描述                               数量        单价        金额
HyperBDR Monthly Subscription      1       US$35.00      US$35.00

合计                               US$35.00
应付金额                           US$35.00
"""
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=text,
        ):
            parsed = parse_invoice_pdf(Path("chinese-invoice.pdf"))

        self.assertEqual(parsed.invoice.invoice_no, "Q3YGPVNT-0001")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-05-29")
        self.assertEqual(parsed.invoice.due_date.isoformat(), "2025-05-29")
        self.assertEqual(parsed.invoice.customer_name, "李坤")
        self.assertEqual(parsed.invoice.customer_contact_person, "李坤")
        self.assertEqual(
            parsed.invoice.customer_contact_email,
            "user@example.cn",
        )
        self.assertEqual(parsed.invoice.contact_person, "")
        self.assertEqual(parsed.invoice.contact_email, "")
        self.assertEqual(parsed.invoice.currency, "USD")
        self.assertEqual(parsed.invoice.total_amount, Decimal("35.00"))
        self.assertEqual(len(parsed.invoice.items), 1)

    def test_delivery_notes_are_not_classified_as_invoices(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=(
                "OnePro Cloud Limited\nDelivery Note\n"
                "Date: 04.09.25\n"
                "DN Number: DN270825_TIME\n"
                "Company : TT DOTCOM SDN BHD (TIME)\n"
                "Name : Fahmi Zainundin\n"
                "Email : fahmi.zainundin@time.com.my\n"
                "Contact Person Email PO#\n"
                "Carrol Yu ecosys@oneprocloud.com 4500104878\n"
                "Item Description Qty Date of Delivery\n"
                "1 HyperBDR Backup & DR License 3 13.01.2026\n"
            ),
        ):
            parsed = parse_invoice_pdf(Path("delivery-note.pdf"))

        self.assertEqual(parsed.document_kind, "delivery_note")
        self.assertEqual(parsed.invoice.invoice_no, "DN270825_TIME")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-09-04")
        self.assertEqual(parsed.invoice.customer_name, "TT DOTCOM SDN BHD (TIME)")
        self.assertEqual(parsed.invoice.purchase_order_no, "4500104878")
        self.assertEqual(parsed.invoice.contact_person, "Carrol Yu")
        self.assertEqual(
            parsed.invoice.contact_email,
            "ecosys@oneprocloud.com",
        )
        self.assertEqual(len(parsed.invoice.items), 1)
        self.assertEqual(
            parsed.invoice.items[0].description,
            "HyperBDR Backup & DR License",
        )
        self.assertEqual(parsed.invoice.items[0].quantity, Decimal("3"))
        self.assertEqual(
            parsed.validation_warnings[0]["code"],
            "delivery_note_detected",
        )

    def test_withholding_tax_documents_are_not_classified_as_invoices(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=(
                "Withholding Tax : OnePro Cloud Limited\n"
                "Amount of tax withheld and date of tax payment\n"
                "2,594.59 Baht\nMay 13, 2025\n"
                "INVOICE PO WHT\n"
                "INV.BDR030325 VPOI68020003 No.0719/ro/002867\n"
            ),
        ):
            parsed = parse_invoice_pdf(Path("withholding-tax.pdf"))

        self.assertEqual(parsed.document_kind, "withholding_tax")
        self.assertEqual(parsed.invoice.invoice_no, "INV.BDR030325")
        self.assertEqual(parsed.invoice.invoice_date.isoformat(), "2025-05-13")
        self.assertEqual(parsed.invoice.currency, "THB")
        self.assertEqual(parsed.invoice.total_amount, Decimal("2594.59"))
        self.assertEqual(
            parsed.validation_warnings[0]["code"],
            "withholding_tax_detected",
        )

    def test_proforma_invoices_are_not_sales_invoices(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=(
                "OnePro Cloud Limited\nProforma Invoice\n"
                "Proforma Invoice Number: PF-100\n"
                "Total Amount: USD 100.00\n"
            ),
        ):
            parsed = parse_invoice_pdf(Path("proforma.pdf"))

        self.assertEqual(parsed.document_kind, "proforma_invoice")
        self.assertEqual(
            parsed.validation_warnings[0]["code"],
            "proforma_invoice_detected",
        )

    def test_refunds_are_not_counted_as_sales_invoices(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=(
                "Refund\nInvoice number QTHXGUNJ-0001\n"
                "Date issued September 26, 2025\n"
                "$35.00 refunded on September 26, 2025\n"
            ),
        ):
            parsed = parse_invoice_pdf(Path("refund.pdf"))

        self.assertEqual(parsed.document_kind, "refund")
        self.assertEqual(
            parsed.validation_warnings[0]["code"],
            "refund_detected",
        )

    def test_actual_invoice_with_proforma_reference_is_kept(self):
        with patch(
            "invoice.parsing.pdf_parser._extract_text",
            return_value=(
                "Commercial Invoice\nInvoice Number: INV-100\n"
                "Proforma Invoice Reference: PF-100\n"
                "Date: 02.01.25\nCompany: Acme Ltd\n"
                "Total Amount: USD 100.00\n"
            ),
        ):
            parsed = parse_invoice_pdf(Path("invoice.pdf"))

        self.assertEqual(parsed.document_kind, "invoice")
        self.assertEqual(parsed.invoice.invoice_no, "INV-100")
