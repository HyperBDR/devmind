/**
 * Run against a mounted quotation's measurement section in a real browser.
 * Fixtures are isolated DOM clones; no application or saved data is changed.
 */
export function verifyQuotationPagination(source, paginateQuotation) {
  const results = []
  const assert = (condition, message) => {
    if (!condition) throw new Error(message)
  }
  const scenarios = [
    { name: 'empty notes', notes: '' },
    { name: 'short notes', notes: 'Short note.' },
    {
      name: 'long bilingual notes',
      notes: 'Reference PDF pagination test — 超长备注分页测试。\n'.repeat(250),
      firstPageNotes: true,
    },
    ...[0, 2, 3].map((lines) => ({
      name: `notes boundary with ${lines} lines available`,
      notes: 'Boundary note content testing remaining page space. '.repeat(100),
      availableLines: lines,
      firstPageNotes: lines >= 3,
    })),
    {
      name: 'short notes fit without splitting',
      notes: 'First line.\nSecond line.',
      availableLines: 2,
      firstPageNotes: true,
      noteFragments: 1,
    },
    {
      name: 'unbroken text and emoji',
      notes: 'LongWord中文👩‍💻'.repeat(1500),
    },
    {
      name: 'many items and subtotals',
      notes: 'After all items.',
      items: 80,
    },
    {
      name: 'description taller than a sheet',
      notes: 'After the long description.',
      description: 'Long description 中文描述 👩‍💻\n'.repeat(220),
    },
    {
      name: 'combined long items and notes',
      notes: 'Notes continuation 中文。\n'.repeat(200),
      items: 35,
      description: 'Long description 中文描述\n'.repeat(100),
    },
  ]
  for (const compact of [true, false]) {
    for (const scenario of scenarios) {
      const fixture = source.cloneNode(true)
      const staging = document.createElement('div')
      const height = compact ? 986 : 1020
      fixture.style.width = compact ? '697px' : '721px'
      fixture.style.padding = compact ? '84px 70px 84px 63px'
        : '87px 73px 87px 65px'
      fixture.querySelectorAll('table').forEach((table) => {
        table.style.fontSize = compact ? '9px' : '9.3px'
      })
      source.parentElement.append(fixture, staging)
      try {
        fixture.querySelector('[data-preview-notes] td').textContent =
          scenario.notes
        const section = fixture.querySelector('.quotation-pdf-section')
        const originalItem = section.querySelector('[data-preview-item]')
        if (scenario.description) {
          originalItem.cells[1].textContent = scenario.description
        }
        if (scenario.items) {
          for (let i = 1; i < scenario.items; i++) {
            const row = originalItem.cloneNode(true)
            row.cells[0].textContent = String(i + 1)
            row.cells[1].textContent = `Unique item ${i + 1}`
            section.tBodies[0].insertBefore(row, section.rows[
              section.rows.length - 1
            ])
          }
        }
        if (scenario.availableLines !== undefined) {
          const title = fixture.querySelector('[data-preview-notes-title]')
          const cell = fixture.querySelector('[data-preview-notes] td')
          const style = getComputedStyle(cell)
          const bottom = height
            - parseFloat(getComputedStyle(fixture).paddingBottom) - 1
          const notesHeight = title.getBoundingClientRect().height
            + scenario.availableLines * parseFloat(style.lineHeight)
            + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
            + parseFloat(style.borderTopWidth)
            + parseFloat(style.borderBottomWidth) + 1
          const titleTop = title.getBoundingClientRect().top
            - fixture.getBoundingClientRect().top
          const spacer = document.createElement('tr')
          const spacerCell = document.createElement('td')
          spacerCell.colSpan = 7
          spacerCell.style.height = `${bottom - titleTop - notesHeight}px`
          spacer.append(spacerCell)
          title.before(spacer)
        }
        const expectedItems = [...fixture.querySelectorAll(
          '[data-preview-item]',
        )].map((row) => row.cells[1].textContent).join('')
        const start = performance.now()
        paginateQuotation(fixture, staging, {
          height,
          continuationTop: compact ? 84 : 87,
          signatureTop: compact ? 79 : 81,
        })
        const elapsed = performance.now() - start
        const pages = [...staging.children]
        for (const page of pages) {
          assert(!page.dataset.previewOversize, `${scenario.name}: oversize`)
          assert(page.scrollHeight <= page.clientHeight + 1,
            `${scenario.name}: clipped page`)
          const bottom = page.querySelector('table').getBoundingClientRect()
            .bottom - page.getBoundingClientRect().top
          assert(bottom <= height - parseFloat(
            getComputedStyle(page).paddingBottom,
          ) + 1, `${scenario.name}: bottom margin overflow`)
          assert(page.textContent.trim(), `${scenario.name}: blank page`)
          for (const table of page.querySelectorAll(
            '.quotation-pdf-section',
          )) {
            assert(table.rows.length > 2,
              `${scenario.name}: orphan table header`)
          }
        }
        assert(staging.querySelectorAll(
          '[data-preview-notes-title]',
        ).length === 1, `${scenario.name}: duplicate/missing title`)
        const titlePage = staging.querySelector(
          '[data-preview-notes-title]',
        ).closest('section')
        if (scenario.firstPageNotes !== undefined) {
          assert((titlePage === pages[0]) === scenario.firstPageNotes,
            `${scenario.name}: wrong notes start page`)
        }
        if (scenario.noteFragments !== undefined) {
          assert(staging.querySelectorAll('[data-preview-notes]').length
            === scenario.noteFragments, `${scenario.name}: unnecessary split`)
        }
        assert(titlePage.querySelector('[data-preview-notes]'),
          `${scenario.name}: orphan notes title`)
        const actualNotes = [...staging.querySelectorAll(
          '[data-preview-notes] td',
        )].map((cell) => cell.textContent).join('')
        assert(actualNotes === scenario.notes,
          `${scenario.name}: changed/lost note text`)
        const actualItems = [...staging.querySelectorAll(
          '[data-preview-item]',
        )].map((row) => row.cells[1].textContent).join('')
        assert(actualItems === expectedItems,
          `${scenario.name}: changed/lost item text`)
        const numericRows = [...staging.querySelectorAll(
          '[data-preview-item]:not([data-preview-continuation])',
        )]
        assert(numericRows.length === fixture.querySelectorAll(
          '[data-preview-item]',
        ).length, `${scenario.name}: repeated amounts`)
        for (const label of [
          'Software subscription subtotal:', 'Others Subtotal:', 'Grand Total:',
        ]) {
          const matching = [...staging.querySelectorAll('td')].filter(
            (cell) => !cell.querySelector('table')
              && cell.textContent.trim() === label,
          )
          assert(matching.length === 1,
            `${scenario.name}: missing/duplicate ${label}`)
        }
        assert(staging.querySelectorAll(
          '[data-preview-signature]',
        ).length === 1, `${scenario.name}: missing/duplicate signature`)
        results.push({
          scenario: scenario.name,
          scale: compact ? 'compact' : 'normal',
          pages: pages.length,
          milliseconds: Math.round(elapsed),
        })
      } finally {
        fixture.remove()
        staging.remove()
      }
    }
  }
  return results
}
