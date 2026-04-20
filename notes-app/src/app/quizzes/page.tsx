import { getAllQuizzes } from '@/lib/quizzes';
import QuizCard from '@/app/components/QuizCard';
import Link from 'next/link';

export default async function QuizzesPage() {
  const quizzes = await getAllQuizzes();

  return (
    <div className="py-8 sm:py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8 sm:mb-10">
          <Link
            href="/"
            className="inline-flex items-center text-gray-400 hover:text-indigo-400 font-medium transition-colors text-xs sm:text-sm mb-4 sm:mb-6"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Notes
          </Link>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Quiz History</h1>
          <p className="text-sm text-gray-400 mt-2">
            {quizzes.length} quiz{quizzes.length !== 1 ? 'zes' : ''} generated so far.
          </p>
        </div>

        {/* Quiz List */}
        {quizzes.length > 0 ? (
          <div className="space-y-6">
            {quizzes.map((quiz) => (
              <QuizCard key={quiz.date} quiz={quiz} />
            ))}
          </div>
        ) : (
          <div className="text-center py-20 bg-gray-900/50 border border-gray-800/60 rounded-xl">
            <p className="text-gray-500">No quizzes yet. They will appear here after the daily quiz workflow runs.</p>
          </div>
        )}
      </div>
    </div>
  );
}
