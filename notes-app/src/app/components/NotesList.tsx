'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';

interface NoteData {
  id: string;
  title: string;
  date: string;
  folder: string;
}

export default function NotesList({ notes }: { notes: NoteData[] }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTrack, setActiveTrack] = useState<string | null>(null);

  // Get unique tracks
  const tracks = useMemo(() => {
    const trackSet = new Set(notes.map((n) => n.category || 'General'));
    return Array.from(trackSet).sort();
  }, [notes]);

  // Filter notes
  const filteredNotes = useMemo(() => {
    return notes.filter((note) => {
      const matchesSearch =
        searchQuery === '' ||
        note.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        note.category.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesTrack =
        activeTrack === null || note.category === activeTrack;
      return matchesSearch && matchesTrack;
    });
  }, [notes, searchQuery, activeTrack]);

  return (
    <div>
      {/* Search Bar */}
      <div className="relative mb-6">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <svg className="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          placeholder="Search notes by title or topic..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all text-sm"
        />
      </div>

      {/* Track Filter Pills - Scrollable on mobile */}
      <div className="flex overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0 sm:overflow-visible sm:pb-0 sm:flex-wrap gap-2 mb-8 no-scrollbar">
        <button
          onClick={() => setActiveTrack(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${activeTrack === null
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25'
              : 'bg-gray-800/60 text-gray-400 hover:bg-gray-800 hover:text-gray-200'
            }`}
        >
          All ({notes.length})
        </button>
        {tracks.map((track) => {
          const count = notes.filter((n) => n.category === track).length;
          return (
            <button
              key={track}
              onClick={() => setActiveTrack(activeTrack === track ? null : track)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${activeTrack === track
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'bg-gray-800/60 text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
            >
              {track} ({count})
            </button>
          );
        })}
      </div>

      {/* Notes Grid */}
      <div className="grid gap-3 sm:gap-4">
        {filteredNotes.map((note) => (
          <Link
            key={note.id}
            href={`/notes/${note.id}`}
            className="group block bg-gray-900/50 border border-gray-800/60 rounded-xl p-4 sm:p-5 hover:bg-gray-800/50 hover:border-gray-700/60 transition-all duration-200"
          >
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3 sm:gap-4">
              <div className="flex-1 min-w-0">
                <h2 className="text-sm sm:text-base font-semibold text-gray-100 group-hover:text-indigo-400 transition-colors line-clamp-2">
                  {note.title}
                </h2>
                <div className="flex items-center gap-3 mt-2 sm:mt-2.5">
                    <span className="px-1.5 py-0.5 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[10px] text-indigo-400 font-bold uppercase tracking-tighter">
                      {note.category}
                    </span>
                    <span className="text-[10px] text-gray-600 truncate max-w-[150px]">
                      {note.folder || 'Root'}
                    </span>
                </div>
              </div>
              <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 sm:gap-1.5">
                <span className="text-[10px] sm:text-xs text-gray-600 whitespace-nowrap order-last sm:order-first">
                  {new Date(note.date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
                {/* Visual marker for unreviewed notes (optional addition) */}
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500/40 sm:hidden"></div>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Empty State */}
      {filteredNotes.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-500 text-sm">
            {searchQuery
              ? `No notes matching "${searchQuery}"`
              : 'No notes found. Create a markdown file to get started!'}
          </p>
        </div>
      )}
    </div>
  );
}
