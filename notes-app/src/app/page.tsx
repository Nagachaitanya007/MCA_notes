import { getSortedNotesData } from '@/lib/notes';
import NotesList from './components/NotesList';

export default async function Home() {
  const allNotesData = await getSortedNotesData();

  // Stats
  const totalNotes = allNotesData.length;
  const uniqueFolders = new Set(allNotesData.map((n) => n.folder || 'Root')).size;
  const latestDate = allNotesData.length > 0
    ? new Date(allNotesData[0].date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : 'N/A';

  return (
    <div className="py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">

        {/* Hero Section */}
        <div className="mb-16 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-6">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
            New notes generated daily by Gemini AI
          </div>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-4">
            Your AI-Powered<br />
            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Study Engine
            </span>
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto">
            NoteForge automatically generates, publishes, and delivers
            interview-grade technical notes every day — covering Java, System Design, AI/ML, and more.
          </p>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-4 mb-12">
          <div className="bg-gray-900/50 border border-gray-800/60 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-white">{totalNotes}</p>
            <p className="text-xs text-gray-500 mt-1">Total Notes</p>
          </div>
          <div className="bg-gray-900/50 border border-gray-800/60 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-white">{uniqueFolders}</p>
            <p className="text-xs text-gray-500 mt-1">Topics</p>
          </div>
          <div className="bg-gray-900/50 border border-gray-800/60 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-white">{latestDate}</p>
            <p className="text-xs text-gray-500 mt-1">Latest Note</p>
          </div>
        </div>

        {/* Notes List with Search */}
        <NotesList notes={allNotesData} />

      </div>
    </div>
  );
}
