import { useEffect, useState } from 'react'

interface Credit {
  file: string
  title: string
  source: string
  author: string
  license: string
  license_url: string
}

// Photo credits come from public/yale/credits.json (written when the photos were downloaded).
export function Credits() {
  const [credits, setCredits] = useState<Credit[]>([])
  useEffect(() => {
    fetch('/yale/credits.json')
      .then((r) => r.json())
      .then(setCredits)
      .catch(() => {})
  }, [])
  return (
    <footer className="credits">
      <div className="credits-strip">
        {credits.map((c) => (
          <a key={c.file} href={c.source} target="_blank" rel="noreferrer" title={`${c.title} · ${c.author} · ${c.license}`}>
            <img src={`/yale/${c.file}`} alt={c.title.replace('File:', '')} />
          </a>
        ))}
      </div>
      <p>
        Campus Customs is a class project, not an official Yale site. Photos from Wikimedia Commons:{' '}
        {credits.map((c, i) => (
          <span key={c.file}>
            <a href={c.source} target="_blank" rel="noreferrer">
              {c.title.replace('File:', '').replace(/\.(jpg|jpeg|png)$/i, '')}
            </a>{' '}
            by {c.author} ({c.license_url ? <a href={c.license_url} target="_blank" rel="noreferrer">{c.license}</a> : c.license})
            {i < credits.length - 1 ? '; ' : '.'}
          </span>
        ))}
      </p>
    </footer>
  )
}
