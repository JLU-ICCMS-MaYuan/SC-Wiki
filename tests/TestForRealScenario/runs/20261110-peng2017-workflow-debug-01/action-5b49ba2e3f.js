if(location.href!=="http://127.0.0.1:5173/upload/tasks/d789acceee124022b3257f84780d1156") throw new Error('论文地址已变化');
return {url:location.href,text:document.body.textContent.slice(0,1200)};