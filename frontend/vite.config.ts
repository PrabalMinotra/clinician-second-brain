import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import federation from '@originjs/vite-plugin-federation';
export default defineConfig({plugins:[react(),federation({name:'second_brain',filename:'remoteEntry.js',exposes:{'./manifest':'./src/manifest.tsx'},shared:['react','react-dom']})],build:{target:'esnext'},server:{proxy:{'/api':'http://127.0.0.1:8000'}}});
