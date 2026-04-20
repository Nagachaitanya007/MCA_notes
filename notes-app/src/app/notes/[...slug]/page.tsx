import Link from 'next/link';
import { getNoteData } from '@/lib/notes';
import { notFound } from 'next/navigation';
import MarkdownRenderer from '@/app/components/MarkdownRenderer';
import TableOfContents from '@/app/components/TableOfContents';
import ReadTracker from '@/app/components/ReadTracker';

interface Props {
  params: Promise<{ slug: string[] }>;
}

export default async function NotePage({ params }: Props) {
  const { slug } = await params;
  const id = slug.join('/');
  
  let noteData;
  try {
    noteData = await getNoteData(id);
    if (!noteData) notFound();
  } catch (e) {
    notFound();
  }

  return (
    <div className="py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Back Link */}
        <div className="mb-8 max-w-4xl">
          <Link
            href="/"
            className="inline-flex items-center text-gray-400 hover:text-indigo-400 font-medium transition-colors text-sm"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Notes
          </Link>
        </div>
        
        {/* Main layout with TOC sidebar */}
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Article */}
          <article className="flex-1 min-w-0 bg-gray-900/50 border border-gray-800/60 rounded-2xl p-6 sm:p-8 md:p-12">
            {/* Header */}
            <header className="mb-10 border-b border-gray-800/60 pb-8">
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white mb-4 tracking-tight leading-tight">
                {noteData.title}
              </h1>
              <div className="flex flex-wrap items-center text-xs sm:text-sm text-gray-500 gap-3 sm:gap-4 mb-4">
                <span className="flex items-center gap-1.5">
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm2 0v8h12V8h-5.828l-2-2H4z" clipRule="evenodd" />
                  </svg>
                  {noteData.folder || 'Root'}
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  {new Date(noteData.date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="whitespace-nowrap">{noteData.readingTime} min read</span>
                </span>
              </div>
              <ReadTracker noteId={noteData.id} />
            </header>
            
            {/* Content with copy-able code blocks */}
            <div className="prose prose-invert prose-indigo prose-sm sm:prose-base md:prose-lg max-w-none overflow-hidden">
              <MarkdownRenderer content={noteData.contentMarkdown || ''} />
            </div>
          </article>

          {/* Table of Contents sidebar */}
          <TableOfContents headings={noteData.headings} />
        </div>
      </div>
    </div>
  );
}
