// index.html sets window.SabrinaHost before this module loads. It provides:
//   storageKey()  this profile's localStorage key for 廣東話 progress
//   changed()     schedule a profile sync to the Mac mini
//   studied()     count today toward the site-wide streak
//   apiRequest(path, opts)  same-origin API call with the session token
//   toast(msg) / isSignedIn() / requestLogin()
export const host = () => window.SabrinaHost;
