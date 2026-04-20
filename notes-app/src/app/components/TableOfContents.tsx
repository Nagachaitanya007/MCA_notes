'use client';

interface Heading {
  text: string;
  level: number;
  slug: string;
}

export default function TableOfContents({ headings }: { headings: Heading[] }) {
  if (headings.length === 0) return null;

  return (
    <nav className="hidden lg:block sticky top-24 w-64 shrink-0">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
        On this page
      </h3>
      <ul className="space-y-1.5 border-l border-gray-800">
        {headings.map((heading) => (
          <li
            key={heading.slug}
            style={{ paddingLeft: `${(heading.level - 2) * 12 + 12}px` }}
          >
            <a
              href={`#${heading.slug}`}
              className="text-sm text-gray-500 hover:text-indigo-400 transition-colors block py-0.5 truncate"
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
