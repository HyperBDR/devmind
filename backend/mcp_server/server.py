"""Read-only MCP tools for authorized quotation and invoice data."""

import calendar
import json
import re
from datetime import date
from urllib.parse import urlsplit

import pymupdf
from django.contrib.auth import get_user_model
from core.pdf_ocr import PdfOcrError, extract_pdf_text_with_ocr
from core.pdf_text import PdfTextExtractionError
from django.conf import settings
from django.db.models import F, Q
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer(
    "DevMind Quote Desk",
    instructions=(
        "Read-only access to quotations, invoices, and source PDF content. "
        "Every tool call is restricted to the authorizing DevMind user's access. "
        "For a quotation query with an explicit date, start by calling "
        "search_quotations with the date exactly as the user wrote it and "
        "limit=20. For a full-month request, continue at offset += limit "
        "until has_more is false, then summarize every page. If total > 0, "
        "show the quotations from results; say the month has no matching "
        "quotations only after all pages are read and total is 0. List quote "
        "number, quote date, customer, project, and amount. Do not retry "
        "alternate date formats or search files before structured search. "
        "Use get_quotation with a result id when full fields or line items "
        "are requested. Distinguish empty results, "
        "permission errors, and tool failures. Never let document search "
        "override quotations returned by this server. search_quotations "
        "returns quotations, not business orders. If the user says 'order' "
        "and quotations are found, show them labeled as quotations; do not "
        "claim there are no related records because no order tool exists. "
        "If the user specifically needs business-order data, explain that "
        "this server cannot query it. Parse common Chinese, English, and "
        "Spanish date and month expressions; pass the user's original date "
        "wording to search_quotations or search_invoices as appropriate. "
        "For invoice or receipt date queries, use search_invoices and its "
        "invoice_date filter. If total > 0, show the returned invoices; "
        "only say no matching invoices after all pages are read and total is "
        "0. Read all pages using offset += limit before summarizing a month. "
        "Do not use document search to override MCP invoice results. "
        "Distinguish empty invoice results, permission errors, and tool "
        "failures. For salesperson filters, pass the person's full name in "
        "the salesperson argument; quotations match issuer_contact_name and "
        "invoices match contact_person or sales_owner equally. Use the "
        "same salesperson argument for invoice handler, responsible person, "
        "or sales owner queries. The returned invoice total applies to "
        "both aliases. Never re-filter invoice results or recalculate total "
        "from raw contact_person/sales_owner values; either can be empty."
    ),
)


def _user(ctx: Context):
    token = get_access_token()
    if not token or not token.subject:
        raise ToolError("A valid DevMind OAuth user is required.")
    user = get_user_model().objects.filter(
        pk=token.subject,
        is_active=True,
    ).first()
    if not user:
        raise ToolError("The authorized DevMind account is unavailable.")
    return user


def _require_robot_scope(scope: str):
    """Enforce module scopes for static robot credentials."""
    token = get_access_token()
    if (
        token
        and token.client_id.startswith("robot:")
        and scope not in token.scopes
    ):
        raise ToolError(f"MCP robot token does not include {scope}.")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _limit(value: int, maximum: int = 20) -> int:
    return min(max(int(value or 10), 1), maximum)


def _offset(value: int) -> int:
    return max(int(value or 0), 0)


_SPANISH_MONTHS = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "setiembre": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}
_MONTH_NUMBERS = {
    month.lower(): number
    for number in range(1, 13)
    for month in (calendar.month_name[number], calendar.month_abbr[number])
}
_MONTH_NUMBERS.update(_SPANISH_MONTHS)
_MONTH_NUMBERS["sept"] = 9
_MONTH_NAMES = "|".join(
    re.escape(name) for name in sorted(_MONTH_NUMBERS, key=len, reverse=True)
)
_MONTH_NAME = rf"(?P<month_name>{_MONTH_NAMES})\.?"


def _month_number(name: str) -> int:
    return _MONTH_NUMBERS[name.lower()]


def _parse_quotation_date(query: str):
    """Return one parsed query date, whether it has a year, and its span."""
    patterns = (
        (
            re.compile(
                rf"(?<!\w)(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
                rf"(?:de\s+)?{_MONTH_NAME}\s+(?:de\s+)?"
                r"(?P<year>\d{4})(?!\d)",
                re.IGNORECASE,
            ),
            True,
        ),
        (
            re.compile(
                rf"(?<!\w){_MONTH_NAME}\s+(?P<day>\d{{1,2}})"
                r"(?:st|nd|rd|th)?(?:,)?\s+(?:of\s+)?"
                r"(?P<year>\d{4})(?!\d)",
                re.IGNORECASE,
            ),
            True,
        ),
        (
            re.compile(
                rf"(?<!\w)(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
                rf"(?:de\s+)?{_MONTH_NAME}(?!\w)",
                re.IGNORECASE,
            ),
            False,
        ),
        (
            re.compile(
                rf"(?<!\w){_MONTH_NAME}\s+(?P<day>\d{{1,2}})"
                r"(?:st|nd|rd|th)?(?!\d)",
                re.IGNORECASE,
            ),
            False,
        ),
        (
            re.compile(
                r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*"
                r"(?P<day>\d{1,2})\s*(?:日|号)?"
            ),
            True,
        ),
        (
            re.compile(
                r"(?<!\d)(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/]"
                r"(?P<day>\d{1,2})(?!\d)"
            ),
            True,
        ),
        (
            re.compile(
                r"(?<!\d)(?P<day>\d{1,2})/(?P<month>\d{1,2})/"
                r"(?P<year>\d{4})(?!\d)"
            ),
            True,
        ),
        (
            re.compile(
                r"(?<!\d)(?P<month>\d{1,2})\s*月\s*"
                r"(?P<day>\d{1,2})\s*(?:日|号)?"
            ),
            False,
        ),
    )
    for pattern, has_year in patterns:
        for match in pattern.finditer(query):
            values = match.groupdict()
            year = int(values["year"]) if has_year else None
            try:
                month = (
                    _month_number(values["month_name"])
                    if values.get("month_name")
                    else int(values["month"])
                )
                parsed = date(
                    year or 2000,
                    month,
                    int(values["day"]),
                )
            except ValueError:
                continue
            return parsed, has_year, match.span()
    return None


def _parse_quotation_month(query: str):
    """Return a month range and its query span, or an invalid month span."""
    patterns = (
        re.compile(r"(?<!\d)(?P<year>\d{4})[-/](?P<month>\d{1,2})(?![-/]\d)"),
        re.compile(
            r"(?<!\d)(?P<year>\d{4})\s*年\s*"
            r"(?P<month>\d{1,2})\s*月(?:份)?"
            r"(?!\s*\d{1,2}\s*(?:日|号))"
        ),
        re.compile(
            rf"(?<!\w){_MONTH_NAME}\s+(?:of\s+)?(?:del?\s+)?"
            r"(?P<year>\d{4})(?!\d)",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?<!\d)(?P<year>\d{{4}})\s+{_MONTH_NAME}(?!\w)",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.search(query)
        if not match:
            continue
        try:
            month = (
                _month_number(match["month_name"])
                if match.groupdict().get("month_name")
                else int(match["month"])
            )
            start = date(int(match["year"]), month, 1)
            if start.month == 12:
                end = date(start.year + 1, 1, 1)
            else:
                end = date(start.year, start.month + 1, 1)
        except ValueError:
            return None, None, match.span()
        return start, end, match.span()
    return None


def _parse_invoice_year(query: str):
    """Return an explicit invoice year and the matched query span."""
    patterns = (
        re.compile(r"(?<!\d)(?P<year>\d{4})\s*年"),
        re.compile(
            r"(?<!\w)(?:in|en)\s+(?P<year>\d{4})(?!\d)",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.search(query)
        if match:
            return int(match["year"]), match.span()
    return None


def _quotation_query_terms(query: str) -> list[str]:
    """Remove common quotation-query wording while retaining filters."""
    query = re.sub(
        r"并?按客户和金额汇总|按客户汇总|按金额汇总|"
        r"请帮我|帮我|查询|查找|搜索|列出|显示|展示|"
        r"查一下|查|一下|"
        r"所有|全部|报价单|报价|本月|当月|月份|汇总|分析|统计|的",
        " ",
        query,
    )
    ignored = {
        "a",
        "all",
        "and",
        "are",
        "can",
        "could",
        "count",
        "dame",
        "buscar",
        "busca",
        "consulta",
        "consultar",
        "cotizacion",
        "cotización",
        "cotizaciones",
        "cuanta",
        "cuantas",
        "cuántas",
        "cuanto",
        "cuantos",
        "cuántos",
        "de",
        "del",
        "during",
        "el",
        "en",
        "every",
        "encuentra",
        "favor",
        "find",
        "for",
        "from",
        "give",
        "hay",
        "how",
        "i",
        "in",
        "la",
        "las",
        "list",
        "los",
        "many",
        "mes",
        "me",
        "month",
        "months",
        "mostrar",
        "muestra",
        "muéstrame",
        "muestrame",
        "number",
        "on",
        "of",
        "para",
        "please",
        "por",
        "presupuesto",
        "presupuestos",
        "quote",
        "quotes",
        "quotation",
        "quotations",
        "que",
        "qué",
        "resumen",
        "resumir",
        "search",
        "show",
        "summary",
        "the",
        "to",
        "toda",
        "todas",
        "todo",
        "todos",
        "there",
        "ver",
        "want",
        "what",
        "which",
        "would",
        "quiero",
        "you",
        "y",
    }
    return [
        term
        for term in re.split(r"[\s，。！？、,:;（）()¿?¡!]+", query)
        if term and term.lower().strip("'\".") not in ignored
    ]


def _has_invalid_invoice_date(query: str) -> bool:
    patterns = (
        r"(?<!\d)\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*" r"(?:日|号)?",
        r"(?<!\d)\d{4}[-/]\d{1,2}[-/]\d{1,2}(?!\d)",
    )
    return any(re.search(pattern, query) for pattern in patterns)


def _invoice_query_terms(query: str) -> list[str]:
    query = re.sub(
        r"票据经办人|票据负责人|销售负责人|经办人|负责人|"
        r"经办|发票|票据|为|年|信息|"
        r"invoices?|receipts?|facturas?|recibos?",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    return _quotation_query_terms(query)


def _quote_data(quote, *, include_items=False):
    result = {
        "id": quote.id,
        "quote_no": quote.quote_no or quote.draft_quote_no,
        "status": quote.status,
        "source_type": quote.source_type,
        "source_quote_no": quote.source_quote_no,
        "version_current": quote.version_current,
        "project_name": quote.project_name,
        "client_company": quote.client_company,
        "product_line": quote.product_line_name or quote.product_line,
        "currency": quote.currency,
        "payment_term_option": quote.payment_term_option,
        "payment_terms": quote.payment_terms,
        "quote_date": quote.quote_date,
        "expire_date": quote.expire_date,
        "tax_label": quote.tax_label,
        "tax_calculation_mode": quote.tax_calculation_mode,
        "vat_rate": quote.vat_rate,
        "vat_amount": quote.vat_amount,
        "deduction_amount": quote.deduction_amount,
        "software_subtotal": quote.software_subtotal,
        "others_subtotal": quote.others_subtotal,
        "subtotal_before_vat": quote.subtotal_before_vat,
        "custom_total_label": quote.custom_total_label,
        "custom_total_amount": quote.custom_total_amount,
        "custom_total_currency": quote.custom_total_currency,
        "grand_total": quote.grand_total,
        "issuer_company_name": quote.issuer_company_name,
        "issuer_contact_name": quote.issuer_contact_name,
        "issuer_contact_email": quote.issuer_contact_email,
        "contact_person": quote.contact_person,
        "email": quote.email,
        "billing_company": quote.billing_company,
        "billing_contact": quote.billing_contact,
        "billing_email": quote.billing_email,
        "remarks_disclaimer": quote.remarks_disclaimer,
        "created_at": quote.created_at,
    }
    if include_items:
        result["items"] = [
            {
                "name": item.name,
                "description": item.description,
                "quantity": item.qty,
                "currency": item.currency,
                "unit_price": item.net_unit_price,
                "amount": item.extended_price,
            }
            for item in quote.items.all()
        ]
    return result


def _quotation_summary(quote):
    return {
        "id": quote.id,
        "quote_no": quote.quote_no or quote.draft_quote_no,
        "status": quote.status,
        "product_line": quote.product_line_name or quote.product_line,
        "quote_date": quote.quote_date,
        "client_company": quote.client_company,
        "project_name": quote.project_name,
        "currency": quote.currency,
        "grand_total": quote.grand_total,
    }


def _invoice_data(invoice, *, include_items=False):
    result = {
        "id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "document_kind": invoice.document_kind,
        "source_type": invoice.source_type,
        "revision_no": invoice.revision_no,
        "product_line": invoice.product_line,
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "seller_name": invoice.seller_name,
        "seller_tax_id": invoice.seller_tax_id,
        "seller_address": invoice.seller_address,
        "seller_website": invoice.seller_website,
        "seller_email": invoice.seller_email,
        "customer_name": invoice.customer_name,
        "customer_tax_id": invoice.customer_tax_id,
        "customer_address": invoice.customer_address,
        "customer_contact_person": invoice.customer_contact_person,
        "customer_contact_email": invoice.customer_contact_email,
        "customer_contact_phone": invoice.customer_contact_phone,
        "contact_person": invoice.contact_person,
        "contact_email": invoice.contact_email,
        "purchase_order_no": invoice.purchase_order_no,
        "payment_terms": invoice.payment_terms,
        "region": invoice.region,
        "currency": invoice.currency,
        "tax_rate": invoice.tax_rate,
        "subtotal_amount": invoice.subtotal_amount,
        "tax_amount": invoice.tax_amount,
        "total_amount": invoice.total_amount,
        "sales_owner": invoice.sales_owner,
        "notes": invoice.notes,
        "additional_notes": invoice.additional_notes,
        "remarks": invoice.remarks,
        "bank_account_name": invoice.bank_account_name,
        "bank_name": invoice.bank_name,
        "bank_address": invoice.bank_address,
        "bank_account_number": invoice.bank_account_number,
        "bank_code": invoice.bank_code,
        "bank_branch_code": invoice.bank_branch_code,
        "bank_swift_code": invoice.bank_swift_code,
        "remittance_instruction": invoice.remittance_instruction,
        "signatory_name": invoice.signatory_name,
        "signatory_title": invoice.signatory_title,
        "created_at": invoice.created_at,
    }
    if include_items:
        result["items"] = [
            {
                "product_name": item.product_name,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "currency": invoice.currency,
                "total_amount": item.total_amount,
            }
            for item in invoice.items.all()
        ]
    return result


@mcp.tool()
def search_quotations(
    query: str = "",
    limit: int = 10,
    offset: int = 0,
    salesperson: str = "",
    ctx: Context = None,
):
    """Search authorized quotations by text, dates, or full months.

    Supports Chinese, English, and Spanish dates and months, including
    2026-08, 2026年8月, August 2026, and agosto de 2026. Month queries
    filter quote_date using a left-closed, right-open range. Specific dates
    and yearless month/day queries remain supported; generated quote numbers
    encode dates as DDMMYY only as a fallback when quote_date is empty. This
    searches quotations, not business orders, invoices, or receipts.

    limit is capped at 20. Use offset and the returned total, limit, and
    has_more values to retrieve every page before summarizing a month.
    salesperson is an optional exact, case-insensitive match against the
    quotation's issuer_contact_name field; surrounding whitespace is ignored.
    It is ANDed with the query text and date filters.
    results contains compact quotation summaries. Use get_quotation with a
    returned id when full fields or line items are requested. Permission
    errors are returned separately from empty results. For a full-month
    analysis, call pages using offset += limit until has_more is false; do not treat one
    page as the full month. If total is positive, present returned quotes;
    only report no matching quotations when every page is read and total is
    zero. Include quote_no, quote_date, client_company, project_name, and
    grand_total. This searches quotations, not business orders. Do not search
    documents for structured quote data unless requested or a field is absent.
    """
    from accounts.access import get_effective_feature_keys
    from quotation.access import filter_accessible_quotations
    from quotation.models import Quotation

    user = _user(ctx)
    _require_robot_scope("quotation:read")
    if "quotation_management" not in get_effective_feature_keys(user):
        return _json({"error": "Quotation platform access is required."})
    queryset = filter_accessible_quotations(
        user,
        Quotation.objects.all(),
    )
    salesperson = salesperson.strip()
    if salesperson:
        queryset = queryset.filter(
            issuer_contact_name__iexact=salesperson
        )
    parsed_date = _parse_quotation_date(query)
    parsed_month = _parse_quotation_month(query) if not parsed_date else None
    text_query = query
    if parsed_date:
        text_query = (
            f"{query[:parsed_date[2][0]]} "
            f"{query[parsed_date[2][1]:]}"
        )
    elif parsed_month:
        text_query = (
            f"{query[:parsed_month[2][0]]} {query[parsed_month[2][1]:]}"
        )

    if parsed_month and parsed_month[0] is None:
        return _json(
            {
                "results": [],
                "total": 0,
                "offset": _offset(offset),
                "limit": _limit(limit),
                "has_more": False,
            }
        )

    terms = _quotation_query_terms(text_query)
    condition = Q()
    if terms:
        for term in terms:
            condition |= (
                Q(quote_no__icontains=term)
                | Q(draft_quote_no__icontains=term)
                | Q(project_name__icontains=term)
                | Q(client_company__icontains=term)
                | Q(payment_terms__icontains=term)
                | Q(issuer_contact_name__icontains=term)
                | Q(contact_person__icontains=term)
                | Q(billing_company__icontains=term)
                | Q(items__name__icontains=term)
                | Q(items__description__icontains=term)
            )

    if parsed_month:
        start, end, _ = parsed_month
        queryset = queryset.filter(quote_date__gte=start, quote_date__lt=end)
        if terms:
            queryset = queryset.filter(condition).distinct()
        queryset = queryset.order_by("-quote_date", "-created_at", "id")
    elif parsed_date:
        requested_date, has_year, _ = parsed_date
        date_filter = Q()
        if has_year:
            date_filter |= Q(quote_date=requested_date)
            number_date = requested_date.strftime("%d%m%y")
        else:
            date_filter |= Q(
                quote_date__month=requested_date.month,
                quote_date__day=requested_date.day,
            )
            number_date = (
                f"{requested_date.day:02d}{requested_date.month:02d}" r"\d{2}"
            )
        date_filter |= Q(quote_date__isnull=True) & (
            Q(quote_no__iregex=rf"{number_date}(?:$|[._])")
            | Q(draft_quote_no__iregex=rf"{number_date}(?:$|[._])")
        )
        queryset = queryset.filter(date_filter)
        if terms:
            queryset = queryset.filter(condition).distinct()
        if has_year:
            queryset = queryset.order_by("-created_at", "id")
        else:
            queryset = queryset.order_by(
                F("quote_date").desc(nulls_last=True), "-created_at", "id"
            )
    elif terms:
        queryset = (
            queryset.filter(condition).distinct().order_by("-created_at", "id")
        )
    else:
        queryset = queryset.order_by("-created_at", "id")

    page_limit = _limit(limit)
    page_offset = _offset(offset)
    total = queryset.count()
    page = list(queryset[page_offset : page_offset + page_limit])
    return _json(
        {
            "results": [_quotation_summary(quote) for quote in page],
            "total": total,
            "offset": page_offset,
            "limit": page_limit,
            "has_more": page_offset + len(page) < total,
        }
    )


@mcp.tool()
def get_quotation(quotation_id: str, ctx: Context = None):
    """Read one quotation and its line items if the user can view it."""
    from accounts.access import get_effective_feature_keys
    from quotation.access import filter_accessible_quotations
    from quotation.models import Quotation

    user = _user(ctx)
    _require_robot_scope("quotation:read")
    if "quotation_management" not in get_effective_feature_keys(user):
        return _json({"error": "Quotation platform access is required."})
    quote = (
        filter_accessible_quotations(
            user,
            Quotation.objects.prefetch_related("items").all(),
        )
        .filter(pk=quotation_id)
        .first()
    )
    if quote is None:
        return _json({"error": "Quotation not found or not accessible."})
    return _json(_quote_data(quote, include_items=True))


@mcp.tool()
def search_invoices(
    query: str = "",
    limit: int = 10,
    offset: int = 0,
    salesperson: str = "",
    ctx: Context = None,
):
    """Search invoices and receipts in the user's invoice visibility scope.

    Supports Chinese, English, Spanish, and numeric month/date queries,
    including 2025年, in 2025, en 2025, 2025年7月, 2025-07, July 2025,
    and julio de 2025. Year and month queries use invoice_date; exact dates
    match invoice_date. Free-text handler searches match contact_person or
    sales_owner. Invoice handler and sales owner are equivalent search
    aliases: pass the full name in salesperson for either wording. This
    argument exactly and case-insensitively matches contact_person OR
    sales_owner; surrounding whitespace is ignored. It is ANDed with query
    text and date filters. The returned total is authoritative for BOTH
    aliases. Do not re-filter records or recalculate total from the raw
    contact_person/sales_owner values: either field can be empty. This searches
    invoices and receipts, not quotations or business orders.

    Each page contains one complete invoice to fit MCP clients that bound
    remote tool results. Use offset and total, limit, and has_more to read
    every page before summarizing a month. Keep all fields and line items in
    results. When total is positive, present the invoice records. Only report
    no matching invoices after all pages are read and total is zero. Do not
    replace MCP results with document search. Distinguish permission errors
    from empty results and tool errors.
    """
    from invoice import permissions as invoice_permissions
    from invoice.models import Invoice

    user = _user(ctx)
    _require_robot_scope("invoice:read")
    if not invoice_permissions.has_invoice_access(user):
        return _json({"error": "Invoice workspace access is required."})
    queryset = Invoice.objects.filter(
        invoice_permissions.invoice_visibility_filter(user)
    )
    salesperson = salesperson.strip()
    if salesperson:
        queryset = queryset.filter(
            invoice_permissions.invoice_responsible_person_filter(
                salesperson
            )
        )

    parsed_date = _parse_quotation_date(query)
    parsed_month = _parse_quotation_month(query) if not parsed_date else None
    parsed_year = (
        _parse_invoice_year(query)
        if not parsed_date and not parsed_month
        else None
    )
    text_query = query
    if parsed_date:
        text_query = f"{query[:parsed_date[2][0]]} {query[parsed_date[2][1]:]}"
    elif parsed_month:
        text_query = (
            f"{query[:parsed_month[2][0]]} {query[parsed_month[2][1]:]}"
        )
    elif parsed_year:
        text_query = (
            f"{query[:parsed_year[1][0]]} "
            f"{query[parsed_year[1][1]:]}"
        )

    page_limit = _limit(limit, maximum=1)
    page_offset = _offset(offset)
    if parsed_month and parsed_month[0] is None:
        return _json(
            {
                "results": [],
                "total": 0,
                "offset": page_offset,
                "limit": page_limit,
                "has_more": False,
            }
        )
    if (
        not parsed_date
        and not parsed_month
        and _has_invalid_invoice_date(query)
    ):
        return _json(
            {
                "results": [],
                "total": 0,
                "offset": page_offset,
                "limit": page_limit,
                "has_more": False,
            }
        )

    terms = _invoice_query_terms(text_query)
    if parsed_month:
        start, end, _ = parsed_month
        queryset = queryset.filter(
            invoice_date__gte=start, invoice_date__lt=end
        )
    elif parsed_year:
        queryset = queryset.filter(invoice_date__year=parsed_year[0])
    elif parsed_date:
        requested_date, has_year, _ = parsed_date
        if has_year:
            queryset = queryset.filter(invoice_date=requested_date)
        else:
            queryset = queryset.filter(
                invoice_date__month=requested_date.month,
                invoice_date__day=requested_date.day,
            )

    if terms:
        condition = Q()
        for term in terms:
            condition |= (
                Q(invoice_no__icontains=term)
                | Q(customer_name__icontains=term)
                | Q(seller_name__icontains=term)
                | Q(contact_person__icontains=term)
                | Q(sales_owner__icontains=term)
                | Q(contact_email__icontains=term)
                | Q(customer_address__icontains=term)
                | Q(purchase_order_no__icontains=term)
                | Q(payment_terms__icontains=term)
                | Q(region__icontains=term)
                | Q(notes__icontains=term)
                | Q(additional_notes__icontains=term)
                | Q(remarks__icontains=term)
                | Q(items__product_name__icontains=term)
                | Q(items__description__icontains=term)
            )
        queryset = queryset.filter(condition).distinct()
    queryset = queryset.prefetch_related("items").order_by(
        "-invoice_date", "-created_at", "-id"
    )
    total = queryset.count()
    page = list(queryset[page_offset : page_offset + page_limit])
    return _json(
        {
            "results": [
                _invoice_data(invoice, include_items=True) for invoice in page
            ],
            "total": total,
            "offset": page_offset,
            "limit": page_limit,
            "has_more": page_offset + len(page) < total,
            "responsibility_fields_equivalent": True,
        }
    )


@mcp.tool()
def get_invoice(invoice_id: str, ctx: Context = None):
    """Read one invoice or receipt if the user can access that record."""
    from invoice import permissions as invoice_permissions
    from invoice.models import Invoice

    user = _user(ctx)
    _require_robot_scope("invoice:read")
    if not invoice_permissions.has_invoice_access(user):
        return _json({"error": "Invoice workspace access is required."})
    invoice = (
        Invoice.objects.filter(
            invoice_permissions.invoice_visibility_filter(user)
        )
        .prefetch_related("items", "documents")
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        return _json({"error": "Invoice not found or not accessible."})
    result = _invoice_data(invoice, include_items=True)
    result["documents"] = [
        {"id": doc.id, "file_name": doc.file_name, "purpose": doc.purpose}
        for doc in invoice.documents.filter(status="active")
    ]
    return _json(result)


def _query_terms(query: str) -> list[str]:
    ignored = {
        "about",
        "after",
        "among",
        "from",
        "have",
        "into",
        "please",
        "that",
        "than",
        "then",
        "there",
        "these",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
        "your",
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "how",
        "who",
        "why",
    }
    return [
        term.casefold()
        for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", query)
        if term.casefold() not in ignored
    ]


def _index_pdf(*, asset=None, invoice_document=None):
    from core.file_hash import hash_file
    from mcp_server.models import McpDocumentPage

    record = asset or invoice_document
    if asset:
        from quotation.services.storage import resolve_document_path

        path = resolve_document_path(asset.storage_key)
        relation = {"quotation_asset": asset}
    else:
        from invoice.services.documents import invoice_storage

        path = invoice_storage().resolve(invoice_document.storage_key)
        relation = {"invoice_document": invoice_document}
    if not path.is_file():
        return
    content_hash = record.content_hash or hash_file(path)
    pages = McpDocumentPage.objects.filter(
        **relation,
        content_hash=content_hash,
    )
    if pages.exists():
        return
    McpDocumentPage.objects.filter(**relation).delete()
    try:
        with pymupdf.open(path) as pdf:
            extracted = [
                (index, page.get_text("text", sort=True).strip())
                for index, page in enumerate(pdf, start=1)
            ]
    except Exception as exc:
        raise PdfTextExtractionError(
            f"Unable to read PDF: {type(exc).__name__}"
        ) from exc
    if not any(text for _, text in extracted):
        try:
            extracted = [(0, extract_pdf_text_with_ocr(path))]
        except (PdfOcrError, TimeoutError):
            return
    McpDocumentPage.objects.bulk_create(
        [
            McpDocumentPage(
                **relation,
                content_hash=content_hash,
                page_number=page_number,
                text=text,
            )
            for page_number, text in extracted
            if text
        ],
        batch_size=100,
    )


def _snippet(text: str, terms: list[str]) -> str:
    folded = text.casefold()
    positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
    start = max(min(positions, default=0) - 180, 0)
    return text[start : start + 700].strip()  # noqa: E203


@mcp.tool()
def search_pdf_content(
    query: str,
    document_type: str = "all",
    limit: int = 10,
    ctx: Context = None,
):
    """Search authorized quotation and invoice PDF copies by full text.

    document_type accepts all, quotations, or invoices. Results quote the
    matching source PDF and page; use the record tool for structured fields.
    """
    from accounts.access import get_effective_feature_keys
    from mcp_server.models import McpDocumentPage

    user = _user(ctx)
    if document_type in {"all", "quotations"}:
        _require_robot_scope("quotation:read")
    if document_type in {"all", "invoices"}:
        _require_robot_scope("invoice:read")
    terms = _query_terms(query)
    if not terms:
        return _json({"results": []})
    if document_type not in {"all", "quotations", "invoices"}:
        return _json(
            {"error": "document_type must be all, quotations, or invoices."}
        )
    quote_access = "quotation_management" in get_effective_feature_keys(user)

    pages = McpDocumentPage.objects.none()
    if document_type in {"all", "quotations"} and quote_access:
        from quotation import models as quotation_models
        from quotation.access import filter_accessible_documents
        from quotation.permissions import can_view_all_quotations

        if can_view_all_quotations(user):
            quote_assets = quotation_models.DocumentAsset.objects.filter(
                doc_type=quotation_models.DocumentType.PDF,
                lifecycle_state=quotation_models.DocumentLifecycleState.ACTIVE,
            )
        else:
            if "quotation_management" not in get_effective_feature_keys(user):
                quote_assets = quotation_models.DocumentAsset.objects.none()
            else:
                quote_assets = filter_accessible_documents(
                    user,
                    quotation_models.DocumentAsset.objects.filter(
                        doc_type=quotation_models.DocumentType.PDF,
                        lifecycle_state=(
                            quotation_models.DocumentLifecycleState.ACTIVE
                        ),
                    ),
                )
        quote_assets = quote_assets.filter(
            Q(quotation__isnull=False)
            | Q(quotation_version__quotation__isnull=False)
            | Q(
                public_attachment__status=(
                    quotation_models.PublicAttachmentStatus.ACTIVE
                )
            )
        ).distinct()
        indexed = set(
            McpDocumentPage.objects.filter(
                quotation_asset__in=quote_assets
            ).values_list("quotation_asset_id", "content_hash")
        )
        # ponytail: lazy indexing adds first-query latency; move this to
        # ingestion jobs when the accessible PDF corpus grows.
        for asset in quote_assets.iterator(chunk_size=100):
            if (
                asset.content_hash
                and (asset.id, asset.content_hash) in indexed
            ):
                continue
            _index_pdf(asset=asset)
        pages = McpDocumentPage.objects.filter(quotation_asset__in=quote_assets)

    if document_type in {"all", "invoices"}:
        from invoice import permissions as invoice_permissions
        from invoice.models import Invoice, InvoiceDocument

        if invoice_permissions.has_invoice_access(user):
            visible_invoices = InvoiceDocument.objects.filter(
                invoice__in=Invoice.objects.filter(
                    invoice_permissions.invoice_visibility_filter(user)
                ),
                status="active",
                document_type="pdf",
            )
            indexed = set(
                McpDocumentPage.objects.filter(
                    invoice_document__in=visible_invoices
                ).values_list("invoice_document_id", "content_hash")
            )
            # ponytail: lazy indexing adds first-query latency; move this to
            # ingestion jobs when the accessible PDF corpus grows.
            for document in visible_invoices.iterator(chunk_size=100):
                if (
                    document.content_hash
                    and (document.id, document.content_hash) in indexed
                ):
                    continue
                _index_pdf(invoice_document=document)
            pages = pages | McpDocumentPage.objects.filter(
                invoice_document__in=visible_invoices
            )

    match = Q()
    for term in terms:
        match |= Q(text__icontains=term)
    hits = []
    for page in pages.filter(match).select_related(
        "quotation_asset__quotation",
        "invoice_document__invoice",
    ):
        text = page.text
        score = sum(text.casefold().count(term) for term in terms)
        if page.quotation_asset_id:
            asset = page.quotation_asset
            record = asset.quotation
            hit = {
                "document_type": "quotation",
                "record_id": getattr(record, "id", None),
                "record_number": (
                    getattr(record, "quote_no", "")
                    or getattr(record, "draft_quote_no", "")
                ),
                "document_id": asset.id,
                "file_name": asset.file_name,
                "source_url": asset.feishu_url or "",
            }
        else:
            document = page.invoice_document
            invoice = document.invoice
            hit = {
                "document_type": "invoice",
                "record_id": invoice.id if invoice else None,
                "record_number": invoice.invoice_no if invoice else "",
                "document_id": document.id,
                "file_name": document.file_name,
                "source_url": document.feishu_url or "",
            }
        hit.update(
            {
                "page": page.page_number or None,
                "score": score,
                "snippet": _snippet(text, terms),
            }
        )
        hits.append(hit)
    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return _json({"results": hits[: _limit(limit)]})


def build_asgi_app():
    """Build the host ASGI router and start the MCP session manager."""
    import contextlib

    from django.core.asgi import get_asgi_application
    from django.core.exceptions import ImproperlyConfigured

    django_app = get_asgi_application()

    from mcp.server.auth.middleware.bearer_auth import (
        BearerAuthBackend,
        RequireAuthMiddleware,
    )
    from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
    from mcp.server.auth.handlers.metadata import MetadataHandler
    from mcp.server.auth.routes import (
        build_metadata,
        build_resource_metadata_url,
        cors_middleware,
        create_auth_routes,
        create_protected_resource_routes,
    )
    from mcp.server.auth.settings import (
        ClientRegistrationOptions,
        RevocationOptions,
    )
    from mcp.server.transport_security import TransportSecuritySettings
    from pydantic import AnyHttpUrl
    from starlette.applications import Starlette
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.routing import Mount
    from starlette.routing import Route
    from mcp_server.oauth import (
        CLIENT_AUTH_METHODS,
        DevMindTokenVerifier,
        READ_SCOPE,
        oauth_provider,
    )

    oauth_urls = {
        "issuer": settings.MCP_OAUTH_ISSUER_URL,
        "resource": settings.MCP_OAUTH_RESOURCE_URL,
        "authorization": settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL,
        "token": settings.MCP_OAUTH_TOKEN_ENDPOINT_URL,
        "registration": settings.MCP_OAUTH_REGISTRATION_ENDPOINT_URL,
        "revocation": settings.MCP_OAUTH_REVOCATION_ENDPOINT_URL,
        "consent": settings.MCP_OAUTH_CONSENT_URL,
    }
    for name, value in oauth_urls.items():
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ImproperlyConfigured(
                f"MCP OAuth {name} URL must be an absolute HTTP(S) URL "
                "without credentials, query, or fragment."
            )
        if not settings.DEBUG and parsed.scheme != "https":
            raise ImproperlyConfigured(
                f"MCP OAuth {name} URL must use HTTPS outside development."
            )
    if settings.MCP_OAUTH_SCOPES != [READ_SCOPE]:
        raise ImproperlyConfigured(
            "MCP_OAUTH_SCOPES currently supports only mcp:read."
        )
    expected_paths = {
        "authorization": "/authorize",
        "token": "/token",
        "registration": "/register",
        "revocation": "/revoke",
    }
    for name, path in expected_paths.items():
        if urlsplit(oauth_urls[name]).path.rstrip("/") != path:
            raise ImproperlyConfigured(
                f"MCP OAuth {name} URL path must be {path}."
            )

    transport_security = TransportSecuritySettings(
        allowed_hosts=settings.MCP_ALLOWED_HOSTS,
    )
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=transport_security,
    )
    resource_url = AnyHttpUrl(settings.MCP_OAUTH_RESOURCE_URL)
    issuer_url = AnyHttpUrl(settings.MCP_OAUTH_ISSUER_URL)
    mcp_app = AuthenticationMiddleware(
        RequireAuthMiddleware(
            AuthContextMiddleware(mcp_app),
            required_scopes=[READ_SCOPE],
            resource_metadata_url=build_resource_metadata_url(resource_url),
        ),
        backend=BearerAuthBackend(
            DevMindTokenVerifier(),
            resource_server_url=resource_url,
        ),
    )
    client_registration_options = ClientRegistrationOptions(
        enabled=True,
        valid_scopes=settings.MCP_OAUTH_SCOPES,
        default_scopes=[READ_SCOPE],
    )
    route_issuer_url = issuer_url
    if issuer_url.scheme == "http" and settings.DEBUG:
        route_issuer_url = AnyHttpUrl("http://localhost/")
    oauth_routes = create_auth_routes(
        oauth_provider,
        issuer_url=route_issuer_url,
        client_registration_options=client_registration_options,
        revocation_options=RevocationOptions(enabled=True),
    )
    revocation_options = RevocationOptions(enabled=True)
    metadata = build_metadata(
        issuer_url,
        None,
        client_registration_options,
        revocation_options,
    )
    metadata.token_endpoint_auth_methods_supported = list(
        CLIENT_AUTH_METHODS
    )
    metadata.authorization_endpoint = AnyHttpUrl(
        settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL
    )
    metadata.token_endpoint = AnyHttpUrl(
        settings.MCP_OAUTH_TOKEN_ENDPOINT_URL
    )
    metadata.registration_endpoint = AnyHttpUrl(
        settings.MCP_OAUTH_REGISTRATION_ENDPOINT_URL
    )
    metadata.revocation_endpoint = AnyHttpUrl(
        settings.MCP_OAUTH_REVOCATION_ENDPOINT_URL
    )
    metadata.revocation_endpoint_auth_methods_supported = list(
        CLIENT_AUTH_METHODS
    )
    issuer_path = urlsplit(settings.MCP_OAUTH_ISSUER_URL).path.rstrip("/")
    metadata_path = (
        "/.well-known/oauth-authorization-server" + issuer_path
    )
    oauth_routes = [
        route
        for route in oauth_routes
        if route.path != "/.well-known/oauth-authorization-server"
    ]
    oauth_routes.insert(
        0,
        Route(
            metadata_path,
            endpoint=cors_middleware(
                MetadataHandler(metadata).handle,
                ["GET", "OPTIONS"],
            ),
            methods=["GET", "OPTIONS"],
        ),
    )
    oauth_routes.extend(
        create_protected_resource_routes(
            resource_url=resource_url,
            authorization_servers=[issuer_url],
            scopes_supported=[READ_SCOPE],
            resource_name="DevMind MCP",
        )
    )
    resource_parts = urlsplit(settings.MCP_OAUTH_RESOURCE_URL)
    if resource_parts.path.strip("/"):
        resource_origin = AnyHttpUrl(
            f"{resource_parts.scheme}://{resource_parts.netloc}/"
        )
        oauth_routes.extend(
            create_protected_resource_routes(
                resource_url=resource_origin,
                authorization_servers=[issuer_url],
                scopes_supported=settings.MCP_OAUTH_SCOPES,
                resource_name="DevMind MCP",
            )
        )

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[
            *oauth_routes,
            Mount("/mcp", app=mcp_app),
            Mount("/", app=django_app),
        ],
        lifespan=lifespan,
    )

    class McpEndpointPath:
        def __init__(self, inner_app):
            self.inner_app = inner_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope["path"] == "/mcp":
                scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
            await self.inner_app(scope, receive, send)

    return McpEndpointPath(app)
