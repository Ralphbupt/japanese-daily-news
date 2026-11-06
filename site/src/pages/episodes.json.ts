import type { APIRoute } from 'astro';
import { episodeList } from '../lib/episode-list';

export const GET: APIRoute = async () => episodeList('main');
