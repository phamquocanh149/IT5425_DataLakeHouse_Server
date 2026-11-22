import { defineConfig } from 'vite';
export default defineConfig({base:'/portal/',server:{proxy:{'/api':'http://127.0.0.1:8010'}},build:{outDir:'dist'}});
