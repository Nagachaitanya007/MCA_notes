import Link from 'next/link';
import { getSortedNotesData } from '@/lib/notes';

export default function Home() {
  const allNotesData = getSortedNotesData();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-3xl mx-auto">
        <header className="mb-12 text-center">
          <h1 className="text-4xl font-extrabold tracking-tight text-indigo-600 dark:text-indigo-400 sm:text-5xl md:text-6xl mb-4">
            Study Notes
          </h1>
          <p className="text-xl text-gray-500 dark:text-gray-400">
            Your personal knowledge base.
          </p>
        </header>

        <ul className="space-y-6">
          {allNotesData.map(({ id, date, title, folder }) => (
            <li key={id} className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden transition-transform transform hover:-translate-y-1 hover:shadow-lg border border-gray-100 dark:border-gray-700">
              <Link href={`/notes/${id}`} className="block p-6">
                <div className="flex flex-col sm:flex-row sm:justify-between sm:items-baseline mb-2">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-1 sm:mb-0">
                    {title}
                  </h2>
                  <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    {new Date(date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                  </span>
                </div>
                <div className="flex items-center text-sm text-indigo-500 dark:text-indigo-400 font-semibold">
                   <svg className="mr-1.5 h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                      <path fillRule="evenodd" d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm2 0v8h12V8h-5.828l-2-2H4z" clipRule="evenodd" />
                    </svg>
                   {folder || 'Root'}
                </div>
              </Link>
            </li>
          ))}
          {allNotesData.length === 0 && (
            <div className="text-center p-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <p className="text-gray-500 dark:text-gray-400">No notes found. Create a markdown file to get started!</p>
            </div>
          )}
        </ul>
      </div>
    </div>
  );
}
