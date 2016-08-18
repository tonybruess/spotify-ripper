import spotipy.util as util
import spotipy.client
import os

def remove_all_from_playlist(username, playlistURI):

    redirect_uri = 'http://www.purple.com'
    client_id = ''
    client_secret = ''

    scope = 'playlist-modify-public'

    p1, p2, p3, p4, rPlaylistID = playlistURI.split(':', 5)

    os.environ["SPOTIPY_CLIENT_ID"] = client_id
    os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
    os.environ["SPOTIPY_REDIRECT_URI"] = redirect_uri

    token = util.prompt_for_user_token(username, scope)

    spotInstance = spotipy.Spotify(auth=token)
    spotInstance.trace = False

    results = spotInstance.user_playlist(username, rPlaylistID, fields="tracks,next")

    tracks = results['tracks']
    track_ids = []
    for i, item in enumerate(tracks['items']):
        track = item['track']
        tid = track['id']
        track_ids.append(tid)
    results = spotInstance.user_playlist_remove_all_occurrences_of_tracks(username, rPlaylistID, track_ids)