import sizes from '../data/audio-bytes.json';

/** Episode mp3s live in R2 (bucket jpnotes-audio, under podcast/), uploaded by tools/audio-sync.py.
 *  podcast.jpnotes.dev/audio/* redirects there (public/_redirects), for feeds and links that kept the old address. */
export const AUDIO_BASE = 'https://audio.jpnotes.dev/podcast';

export const audioUrl = (id: string) => `${AUDIO_BASE}/${id}.mp3`;

/** File size in bytes, for the RSS enclosure (0 if the episode was never synced). */
export const audioBytes = (id: string): number => (sizes as Record<string, number>)[id] ?? 0;
