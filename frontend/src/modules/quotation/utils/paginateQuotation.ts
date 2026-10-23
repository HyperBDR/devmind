/// <reference lib="es2022.intl" />

interface PageLayout {
  height: number
  continuationTop: number
  signatureTop: number
}

/** Paginate already-rendered quotation markup using browser layout. */
export function paginateQuotation(
  source: HTMLElement,
  staging: HTMLElement,
  layout: PageLayout,
): void {
  const sourceTable = source.querySelector('table')!
  const sourceBody = sourceTable.tBodies[0]
  let page: HTMLElement
  let table: HTMLTableElement
  let body!: HTMLTableSectionElement
  let nested: {
    template: HTMLTableElement
    body: HTMLTableSectionElement
    wrapper: HTMLTableRowElement
  } | null = null

  function newPage(signature = false): void {
    const first = staging.childElementCount === 0
    page = source.cloneNode(false) as HTMLElement
    page.style.height = `${layout.height}px`
    page.dataset.previewPage = String(staging.childElementCount + 1)
    if (!first) {
      page.style.paddingTop = `${
        signature ? layout.signatureTop : layout.continuationTop
      }px`
    } else {
      const logo = source.querySelector(':scope > img')
      if (logo) page.append(logo.cloneNode(true))
    }
    table = sourceTable.cloneNode(false) as HTMLTableElement
    table.append(sourceTable.querySelector('colgroup')!.cloneNode(true))
    body = sourceBody.cloneNode(false) as HTMLTableSectionElement
    table.append(body)
    page.append(table)
    staging.append(page)
    nested = null
  }

  function fits(): boolean {
    const style = getComputedStyle(page)
    const bottom = page.getBoundingClientRect().top + layout.height
      - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth)
    return table.getBoundingClientRect().bottom <= bottom + 0.5
  }

  function append(
    rows: HTMLTableRowElement[],
    template?: HTMLTableElement,
  ): () => void {
    let destination = body
    if (template) {
      if (nested?.template !== template) {
        const wrapper = template.closest('td')!.parentElement!
          .cloneNode(false) as HTMLTableRowElement
        const cell = template.closest('td')!
          .cloneNode(false) as HTMLTableCellElement
        const section = template.cloneNode(false) as HTMLTableElement
        section.append(template.querySelector('colgroup')!.cloneNode(true))
        const sectionBody = template.tBodies[0]
          .cloneNode(false) as HTMLTableSectionElement
        for (const header of Array.from(template.rows).slice(0, 2)) {
          sectionBody.append(header.cloneNode(true))
        }
        section.append(sectionBody)
        cell.append(section)
        wrapper.append(cell)
        body.append(wrapper)
        nested = { template, body: sectionBody, wrapper }
      }
      destination = nested.body
    } else {
      nested = null
    }
    destination.append(...rows)
    return () => {
      rows.forEach((row) => row.remove())
      if (nested && nested.body.rows.length === 2) {
        nested.wrapper.remove()
        nested = null
      }
    }
  }

  function clone(row: HTMLTableRowElement): HTMLTableRowElement {
    return row.cloneNode(true) as HTMLTableRowElement
  }

  function place(
    originals: HTMLTableRowElement[],
    template?: HTMLTableElement,
    textColumn?: number,
    signature = false,
  ): void {
    const splitNotesHere = textColumn !== undefined
      && originals[0].hasAttribute('data-preview-notes-title')
    let rows = originals.map(clone)
    let remove = append(rows, template)
    if (fits()) return
    if (!splitNotesHere) {
      remove()
      if (body.rows.length) newPage(signature)
      rows = originals.map(clone)
      remove = append(rows, template)
      if (fits()) return
    }

    if (textColumn === undefined) {
      // shortcut: oversized metadata expands the sheet; split if required.
      page.style.height = 'auto'
      page.style.minHeight = `${layout.height}px`
      page.dataset.previewOversize = 'true'
      return
    }
    remove()
    const original = originals[originals.length - 1]
    const text = original.cells[textColumn].textContent || ''
    if (!text) {
      newPage()
      append(originals.map(clone), template)
      return
    }
    const characters = Array.from(
      new Intl.Segmenter(undefined, { granularity: 'grapheme' })
        .segment(text),
      (part) => part.segment,
    )
    let offset = 0
    while (offset < characters.length) {
      const row = clone(original)
      if (offset && template) {
        Array.from(row.cells).forEach((cell, index) => {
          if (index !== textColumn) cell.textContent = ''
        })
        row.dataset.previewContinuation = 'true'
      }
      const prefix = offset ? [] : originals.slice(0, -1).map(clone)
      const undo = append([...prefix, row], template)
      const cell = row.cells[textColumn]
      let low = 0
      let high = characters.length - offset
      while (low < high) {
        const middle = Math.ceil((low + high) / 2)
        cell.textContent = characters.slice(offset, offset + middle).join('')
        if (fits()) low = middle
        else high = middle - 1
      }
      if (!low) {
        undo()
        if (splitNotesHere && body.rows.length) {
          newPage()
          continue
        }
        throw new Error('Quotation page cannot fit a line of text')
      }
      // Prefer a word boundary without dropping whitespace or punctuation.
      let end = offset + low
      if (end < characters.length) {
        for (let i = end - 1; i > Math.max(offset, end - 40); i--) {
          if (/\s/u.test(characters[i])) {
            end = i + 1
            break
          }
        }
      }
      cell.textContent = characters.slice(offset, end).join('')
      if (splitNotesHere && offset === 0 && end < characters.length) {
        const range = document.createRange()
        range.selectNodeContents(cell)
        const lines = new Set(
          Array.from(range.getClientRects())
            .filter((rect) => rect.width > 0)
            .map((rect) => Math.round(rect.top)),
        )
        if (lines.size < 3) {
          undo()
          if (!body.rows.length) {
            throw new Error('Quotation page cannot fit three note lines')
          }
          newPage()
          continue
        }
      }
      offset = end
      if (offset < characters.length) newPage()
    }
  }

  newPage()
  const rows = Array.from(sourceBody.rows)
  for (let index = 0; index < rows.length; index++) {
    const row = rows[index]
    const section = row.querySelector<HTMLTableElement>(
      'table.quotation-pdf-section',
    )
    if (section) {
      for (const item of Array.from(section.rows).slice(2)) {
        place([item], section, item.hasAttribute('data-preview-item') ? 1
          : undefined)
      }
    } else if (row.hasAttribute('data-preview-notes-title')) {
      place([row, rows[++index]], undefined, 0)
    } else if (row.hasAttribute('data-preview-signature')) {
      place(rows.slice(index), undefined, undefined, true)
      break
    } else {
      // Blank spacing rows must not create empty continuation pages.
      if (!row.textContent?.trim() && !row.querySelector('img')) {
        if (body.rows.length || staging.childElementCount === 1) {
          const undo = append([clone(row)])
          if (!fits()) undo()
        }
      } else {
        place([row])
      }
    }
  }
}
