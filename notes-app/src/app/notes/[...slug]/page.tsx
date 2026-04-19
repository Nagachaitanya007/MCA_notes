import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import { getNoteData } from '@/lib/notes';
import { notFound } from 'next/navigation';

interface Props {
  params: Promise<{ slug: string[] }>;
}

export default async function NotePage({ params }: Props) {
  const { slug } = await params;
  const id = slug.join('/');
  
  let noteData;
  try {
    noteData = getNoteData(id);
  } catch (e) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <Link href="/" className="inline-flex items-center text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-semibold transition-colors">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
            Back to Notes
          </Link>
        </div>
        
        <article className="bg-white dark:bg-gray-800 shadow rounded-lg p-8 md:p-12 border border-gray-100 dark:border-gray-700">
          <header className="mb-10 border-b border-gray-200 dark:border-gray-700 pb-8">
            <h1 className="text-3xl md:text-5xl font-extrabold text-gray-900 dark:text-white mb-4 tracking-tight">
              {noteData.title}
            </h1>
            <div className="flex flex-wrap items-center text-sm text-gray-500 dark:text-gray-400 gap-4">
              <span className="flex items-center">
                 <svg className="mr-1.5 h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true"><path fillRule="evenodd" d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm2 0v8h12V8h-5.828l-2-2H4z" clipRule="evenodd" /></svg>
                 {noteData.folder || 'Root'}
              </span>
              <span className="flex items-center">
                 <svg className="mr-1.5 h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                 {new Date(noteData.date).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
              </span>
            </div>
          </header>
          
          <div className="prose prose-indigo dark:prose-invert prose-lg max-w-none">
            <ReactMarkdown>{noteData.contentMarkdown || ''}</ReactMarkdown>
          </div>
        </article>
      </div>
    </div>
  );
}
