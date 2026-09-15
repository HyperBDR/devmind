from django.contrib import admin

from invoice.models import (
    Invoice,
    InvoiceAccessGrant,
    InvoiceDocument,
    InvoiceItem,
    InvoiceNumberSequence,
    InvoiceParseResult,
)


admin.site.register(Invoice)
admin.site.register(InvoiceAccessGrant)
admin.site.register(InvoiceItem)
admin.site.register(InvoiceNumberSequence)
admin.site.register(InvoiceDocument)
admin.site.register(InvoiceParseResult)
