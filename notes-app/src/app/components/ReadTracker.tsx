'use client';

import { useState, useEffect } from 'react';

export default function ReadTracker({ noteId }: { noteId: string }) {
  const [isRead, setIsRead] = useState(false);

  useEffect(() => {
    const readNotes = JSON.parse(localStorage.getItem('readNotes') || '[]');
    setIsRead(readNotes.includes(noteId));
  }, [noteId]);

  const toggleRead = () => {
    const readNotes: string[] = JSON.parse(localStorage.getItem('readNotes') || '[]');
    let updated: string[];
    if (readNotes.includes(noteId)) {
      updated = readNotes.filter((id: string) => id !== noteId);
    } else {
      updated = [...readNotes, noteId];
    }
    localStorage.setItem('readNotes', JSON.stringify(updated));
    setIsRead(!isRead);
  };

  return (
    <button
      onClick={toggleRead}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
        isRead
          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
          : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600 hover:text-gray-300'
      }`}
    >
      {isRead ? (
        <>
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          Reviewed
        </>
      ) : (
        <>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Mark as Reviewed
        </>
      )}
    </button>
  );
}
